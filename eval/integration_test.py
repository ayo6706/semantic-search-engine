import os
import sys
import time
import asyncio
import httpx
import subprocess
import shutil

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from eval.generate_test_data import generate_all_test_data

API_URL = "http://localhost:8080/api/v1"

async def main():
    print("=== STARTING END-TO-END INTEGRATION TEST ===")
    
    # 1. Create temporary directory and generate test PDFs
    temp_dir = "eval/temp_integration_pdfs"
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
    os.makedirs(temp_dir, exist_ok=True)
    
    print(f"Generating test PDFs in {temp_dir}...")
    generate_all_test_data(temp_dir)
    
    uploaded_doc_ids = []
    
    try:
        # 2. Upload PDFs to the API
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Check API health first
            print("Checking API health...")
            try:
                health_resp = await client.get(f"{API_URL}/health")
                print(f"API Health response: {health_resp.status_code} - {health_resp.json()}")
                assert health_resp.status_code == 200, "API is not healthy"
            except Exception as e:
                print(f"API connection failed: {e}")
                sys.exit(1)
                
            # Upload files
            for filename in os.listdir(temp_dir):
                if not filename.endswith(".pdf"):
                    continue
                file_path = os.path.join(temp_dir, filename)
                print(f"Uploading {filename}...")
                with open(file_path, "rb") as f:
                    response = await client.post(
                        f"{API_URL}/documents",
                        files={"file": (filename, f, "application/pdf")}
                    )
                assert response.status_code == 200, f"Upload failed for {filename}: {response.text}"
                doc_data = response.json()
                doc_id = doc_data["id"]
                uploaded_doc_ids.append(doc_id)
                print(f"Uploaded {filename} successfully. ID: {doc_id}, status: {doc_data['status']}")
            
            # 3. Poll document statuses until ready
            print("Polling document statuses until ready...")
            start_time = time.time()
            timeout = 120.0  # Allow plenty of time for embedding and chunking
            pending_ids = list(uploaded_doc_ids)
            
            while pending_ids and (time.time() - start_time) < timeout:
                await asyncio.sleep(3.0)
                still_pending = []
                for doc_id in pending_ids:
                    resp = await client.get(f"{API_URL}/documents/{doc_id}")
                    assert resp.status_code == 200, f"Failed to get document status for {doc_id}"
                    status = resp.json()["status"]
                    print(f"Document {doc_id} status: {status}")
                    if status == "failed":
                        raise RuntimeError(f"Ingestion failed for document {doc_id}")
                    if status != "ready":
                        still_pending.append(doc_id)
                pending_ids = still_pending
                
            if pending_ids:
                raise TimeoutError(f"Ingestion timed out for documents: {pending_ids}")
            
            print("All documents ingested successfully!")
            
            # 4. Verify search modes via API
            print("Verifying search modes via API...")
            test_queries = [
                ("billing frequency monthly", "payment_agreement.pdf"),
                ("forty hours per week", "employment_contract.pdf"),
                ("limitation of liability", "terms_of_service.pdf")
            ]
            
            for query, expected_doc in test_queries:
                print(f"\nTesting search query: '{query}'")
                for mode in ["dense", "sparse", "hybrid"]:
                    print(f"  Running {mode} search...")
                    search_payload = {
                        "query": query,
                        "search_mode": mode,
                        "use_reranker": True,
                        "top_k": 5
                    }
                    
                    # Test first request (cache miss)
                    t0 = time.time()
                    resp = await client.post(f"{API_URL}/search", json=search_payload)
                    t1 = time.time()
                    assert resp.status_code == 200, f"Search failed: {resp.text}"
                    res_data = resp.json()
                    assert "results" in res_data
                    assert len(res_data["results"]) > 0, "No results returned"
                    
                    # Verify fields are present
                    first_result = res_data["results"][0]
                    assert "chunk_id" in first_result
                    assert "doc_filename" in first_result
                    assert "snippet" in first_result
                    assert "score" in first_result
                    
                    # Check highlighting
                    assert "<mark>" in first_result["snippet"].lower(), "Snippet highlighting not present"
                    
                    print(f"    Mode {mode} search returned {len(res_data['results'])} results. Top doc: {first_result['doc_filename']}. Latency: {(t1-t0)*1000:.1f}ms")
                    
                    # Test second request (cache hit)
                    t2 = time.time()
                    resp_cache = await client.post(f"{API_URL}/search", json=search_payload)
                    t3 = time.time()
                    assert resp_cache.status_code == 200
                    res_data_cache = resp_cache.json()
                    print(f"    Cached Mode {mode} search returned. Latency: {(t3-t2)*1000:.1f}ms (originally {(t1-t0)*1000:.1f}ms)")
                    # The cached latency reported inside response should be the same as the original execution
                    assert res_data_cache["latency_ms"] == res_data["latency_ms"]

            # 5. Run the evaluation suite
            print("\nRunning the evaluation suite (eval/runner.py)...")
            runner_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "runner.py"))
            env = os.environ.copy()
            env["PYTHONPATH"] = "backend"
            result = subprocess.run(
                [sys.executable, runner_path],
                capture_output=True,
                text=True,
                env=env,
                cwd=os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
            )
            print(result.stdout)
            if result.returncode != 0:
                print(f"Evaluation runner failed with return code {result.returncode}")
                print(result.stderr)
                raise RuntimeError("Evaluation runner failed")
                
            # Verify eval/report.md exists and contains the results table
            report_path = "eval/report.md"
            assert os.path.exists(report_path), "Evaluation report.md was not generated"
            with open(report_path, "r", encoding="utf-8") as f:
                report_content = f.read()
            assert "Retrieval Ablation Evaluation Report" in report_content, "Report is missing title"
            assert "Dense Only" in report_content, "Report is missing Dense config"
            assert "Sparse Only" in report_content, "Report is missing Sparse config"
            print("Evaluation suite completed and verified report.md successfully!")
            
    except Exception as e:
        print(f"\nERROR: Integration test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
        
    finally:
        # 6. Clean up uploaded documents
        print("\nCleaning up uploaded documents...")
        async with httpx.AsyncClient(timeout=30.0) as client:
            for doc_id in uploaded_doc_ids:
                print(f"Deleting document {doc_id}...")
                resp = await client.delete(f"{API_URL}/documents/{doc_id}")
                print(f"Delete response: {resp.status_code}")
                assert resp.status_code == 204 or resp.status_code == 404, f"Delete failed: {resp.status_code}"
                
        # 7. Clean up temporary directory
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            print(f"Removed temporary directory {temp_dir}")
            
    print("\n=== E2E INTEGRATION TEST COMPLETED SUCCESSFULLY ===")

if __name__ == "__main__":
    asyncio.run(main())
