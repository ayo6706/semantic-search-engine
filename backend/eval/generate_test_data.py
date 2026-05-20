import os
import fitz

def generate_pdf(filename: str, pages_content: list[str], output_dir: str):
    """Generate a PDF file with pages containing specified text content."""
    os.makedirs(output_dir, exist_ok=True)
    filepath = os.path.join(output_dir, filename)
    
    doc = fitz.open()
    for text in pages_content:
        page = doc.new_page()
        # Insert text with safety margins (50, 50)
        # Using a standard font to avoid external dependency issues
        page.insert_text(fitz.Point(50, 50), text, fontsize=11, fontname="helv")
    
    doc.save(filepath)
    doc.close()
    print(f"Generated PDF: {filepath}")

def generate_all_test_data(output_dir: str = "uploads"):
    """Generate the 3 test PDFs required for retrieval evaluation with proper line-wrapping."""
    docs = {
        "payment_agreement.pdf": [
            # Page 1
            "PAYMENT SERVICE AGREEMENT\n\n"
            "This Payment Service Agreement (the 'Agreement') is entered into\n"
            "by and between the Service Provider and the Client.\n"
            "The billing frequency and schedule under this agreement shall be\n"
            "strictly monthly. Invoices will be generated and delivered to the\n"
            "client on the first day of each calendar month.\n"
            "The accepted payment methods for any transactions under this Agreement\n"
            "are bank wire transfer, credit card, and direct debit. Cash payments\n"
            "are explicitly not accepted.",
            
            # Page 2
            "Article 4.2: Late Payment Penalty and Fees\n\n"
            "Any invoice not paid within the due date grace period of ten\n"
            "business days shall be considered overdue.\n"
            "A late payment interest rate penalty of 1.5% per month will\n"
            "automatically accrue on any outstanding balances.\n"
            "Additionally, a flat late fee terms of $50 will be charged\n"
            "for administrative processing.",
            
            # Page 3
            "Article 4.3: Billing Disputes and Refunds\n\n"
            "If the Client disputes any portion of an invoice, they must notify\n"
            "the Provider within 5 business days using the electronic invoice\n"
            "delivery email.\n"
            "The refund policy for prepaid services specifies that refunds are\n"
            "only available if requested within 14 days of purchase.\n"
            "An early payment discount of 2% is offered if payment is cleared\n"
            "within 5 business days of invoice date."
        ],
        "employment_contract.pdf": [
            # Page 1
            "EMPLOYMENT CONTRACT\n\n"
            "This Employment Contract is made between the Employer and the Employee.\n"
            "The Employee's standard weekly working hours shall be exactly\n"
            "forty hours per week, excluding lunch breaks.\n"
            "The monthly base salary payment date is the 25th day of each\n"
            "calendar month.\n"
            "The initial probationary period duration is set to six months\n"
            "from the start date.",
            
            # Page 2
            "Article 5: Intellectual Property and Non-Disclosure\n\n"
            "The Employee agrees that all intellectual property rights and\n"
            "ownership assignment of work created during employment belong\n"
            "solely to the Employer.\n"
            "The non-disclosure and confidentiality agreement requires that\n"
            "confidential information must not be disclosed to any third party.\n"
            "The confidentiality duration and obligations shall survive\n"
            "termination for a period of five years.",
            
            # Page 3
            "Article 6: Termination, Sick Leave, and Benefits\n\n"
            "The termination notice period requirements state that either party\n"
            "may terminate this agreement by giving 30 days written notice.\n"
            "The employee's annual leave entitlement paid time off is 25 days\n"
            "per calendar year.\n"
            "For sick leave notice and doctor note, the employee must notify\n"
            "their manager by 9:00 AM on the first day of absence."
        ],
        "terms_of_service.pdf": [
            # Page 1
            "TERMS OF SERVICE\n\n"
            "Welcome to our platform. These Terms of Service govern your use\n"
            "of our website and services.\n"
            "The minimum age requirement to use service is eighteen years old.\n"
            "The account suspension and termination conditions allow the platform\n"
            "to suspend any account that violates our acceptable use policy\n"
            "prohibited activities.",
            
            # Page 2
            "Article 7: Limitation of Liability and Indemnification\n\n"
            "Our limitation of liability maximum cap is strictly limited to the\n"
            "total fees paid by the user in the past twelve months.\n"
            "The governing law state of New York shall govern all disputes\n"
            "arising out of these terms.\n"
            "The dispute resolution binding arbitration process will be handled\n"
            "by the American Arbitration Association.",
            
            # Page 3
            "Article 7.3: Specific Exclusions\n\n"
            "Article 7.3 specifications: Under no circumstances shall the platform\n"
            "be liable for indirect, incidental, special, or consequential damages.\n"
            "These terms include a class action waiver in arbitration, meaning\n"
            "all disputes must be resolved on an individual basis.\n"
            "The force majeure clause excuses performance delays caused by\n"
            "acts of God, war, or natural disasters."
        ]
    }
    
    for filename, pages in docs.items():
        generate_pdf(filename, pages, output_dir)

if __name__ == "__main__":
    import sys
    # Use specified output directory or default 'uploads'
    out = sys.argv[1] if len(sys.argv) > 1 else "uploads"
    generate_all_test_data(out)
