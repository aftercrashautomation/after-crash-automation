import imaplib
import email
import os
import time
import smtplib
import json
from email.message import EmailMessage
from pdfrw import PdfReader, PdfWriter, PdfDict
from openai import OpenAI

EMAIL_USER = os.environ["EMAIL_USER"]
EMAIL_PASS = os.environ["EMAIL_PASS"]
OPENAI_KEY = os.environ["OPENAI_KEY"]

IMAP_SERVER = "imap.gmail.com"
SMTP_SERVER = "smtp.gmail.com"

client = OpenAI(api_key=OPENAI_KEY)

def extract_data(email_body):
    prompt = f"""
    Extract the following fields from this email.
    If missing, leave blank.
    Return VALID JSON only.

    renters_name
    renters_address
    renters_phone
    at_fault_insurer
    at_fault_rego
    at_fault_claim_number
    at_fault_make_model

    Email:
    {email_body}
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )

    return json.loads(response.choices[0].message.content)

def fill_pdf(data):
    template = PdfReader("rental_template.pdf")

    for page in template.pages:
        annotations = page.get('/Annots')
        if annotations:
            for annotation in annotations:
                if annotation.get('/T'):
                    key = annotation['/T'][1:-1]
                    if key in data:
                        annotation.update(
                            PdfDict(V=str(data.get(key, "")))
                        )

    PdfWriter().write("completed_rental.pdf", template)

def send_email():
    msg = EmailMessage()
    msg["Subject"] = "After Crash - Completed Rental Agreement"
    msg["From"] = EMAIL_USER
    msg["To"] = EMAIL_USER

    msg.set_content("Attached is the completed rental agreement. Please review before sending.")

    with open("completed_rental.pdf", "rb") as f:
        msg.add_attachment(
            f.read(),
            maintype="application",
            subtype="pdf",
            filename="AfterCrash_Rental_Agreement.pdf"
        )

    with smtplib.SMTP_SSL(SMTP_SERVER, 465) as smtp:
        smtp.login(EMAIL_USER, EMAIL_PASS)
        smtp.send_message(msg)

def check_email():
    mail = imaplib.IMAP4_SSL(IMAP_SERVER)
    mail.login(EMAIL_USER, EMAIL_PASS)
    mail.select("inbox")

    status, messages = mail.search(None, '(UNSEEN)')

    for num in messages[0].split():
        status, data = mail.fetch(num, '(RFC822)')
        msg = email.message_from_bytes(data[0][1])

        body = ""

        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    body = part.get_payload(decode=True).decode(errors="ignore")
        else:
            body = msg.get_payload(decode=True).decode(errors="ignore")

        extracted = extract_data(body)
        fill_pdf(extracted)
        send_email()

    mail.logout()

while True:
    check_email()

    time.sleep(60)
