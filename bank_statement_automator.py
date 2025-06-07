import argparse
import os
import base64
import json
import requests
from typing import List

# Placeholder for Google Drive integration
try:
    from pydrive2.auth import GoogleAuth
    from pydrive2.drive import GoogleDrive
except ImportError:
    GoogleAuth = None
    GoogleDrive = None

# Placeholder for SendGrid integration
try:
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Mail, Attachment, FileContent, FileName, FileType, Disposition
except ImportError:
    SendGridAPIClient = None
    Mail = None


def fetch_statement(format: str, start_date: str, end_date: str, token: str) -> bytes:
    """Fetch statement file from Banco Inter API.
    This function contains placeholders for demonstration purposes."""
    url = f"https://api.bancointer.com.br/bankstatements/{format}"  # Placeholder URL
    headers = {
        "Authorization": f"Bearer {token}",
    }
    params = {
        "dataInicio": start_date,
        "dataFim": end_date,
    }
    # In a real implementation, you would perform:
    # response = requests.get(url, headers=headers, params=params)
    # response.raise_for_status()
    # return response.content
    print(f"Fetching {format} statement from {start_date} to {end_date} ...")
    return b"PLACEHOLDER_FILE_CONTENT"


def save_file(content: bytes, path: str):
    with open(path, "wb") as f:
        f.write(content)
    print(f"Saved file {path}")


def upload_to_drive(filepath: str, drive_credentials: str) -> str:
    if GoogleAuth is None:
        raise RuntimeError("pydrive2 is required for Google Drive uploads")
    gauth = GoogleAuth()
    gauth.credentials = None  # Replace with logic to load credentials
    # gauth.LoadCredentialsFile(drive_credentials)
    drive = GoogleDrive(gauth)
    file_drive = drive.CreateFile({"title": os.path.basename(filepath)})
    file_drive.SetContentFile(filepath)
    file_drive.Upload()
    print(f"Uploaded {filepath} to Google Drive")
    return file_drive["id"]


def send_email(files: List[str], recipients: List[str], api_key: str, subject: str):
    if SendGridAPIClient is None:
        raise RuntimeError("sendgrid package is required for sending emails")
    message = Mail(
        from_email="noreply@example.com",
        to_emails=recipients,
        subject=subject,
        html_content="Please find attached your bank statements.",
    )
    for path in files:
        with open(path, "rb") as f:
            data = f.read()
        encoded = base64.b64encode(data).decode()
        attachment = Attachment(
            FileContent(encoded),
            FileName(os.path.basename(path)),
            FileType("application/octet-stream"),
            Disposition("attachment"),
        )
        message.add_attachment(attachment)
    sg = SendGridAPIClient(api_key)
    sg.send(message)
    print(f"Email sent to {', '.join(recipients)}")


def get_bank_token(creds_path: str) -> str:
    """Retrieve an OAuth token from Banco Inter using stored credentials."""
    with open(creds_path) as f:
        creds = json.load(f)

    request_body = (
        f"client_id={creds['client_id']}"
        f"&client_secret={creds['client_secret']}"
        f"&scope=extrato.read"
        f"&grant_type=client_credentials"
    )

    response = requests.post(
        "https://cdpj.partners.bancointer.com.br/oauth/v2/token",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        cert=(creds["cert"], creds["key"]),
        data=request_body,
    )
    response.raise_for_status()
    token = response.json().get("access_token")
    if not token:
        raise RuntimeError("Token não encontrado na resposta do Banco Inter")
    return token


def parse_args():
    parser = argparse.ArgumentParser(description="Banco Inter statement automator")
    parser.add_argument("--de", dest="start", required=True, help="Data de (YYYY-MM-DD)")
    parser.add_argument("--ate", dest="end", required=True, help="Data até (YYYY-MM-DD)")
    parser.add_argument("--output-dir", default="./output", help="Diretório para salvar arquivos")
    parser.add_argument(
        "--bank-creds",
        required=True,
        help="Arquivo JSON com client_id, client_secret, cert e key do Banco Inter",
    )
    parser.add_argument("--drive-creds", required=True, help="Credenciais do Google Drive")
    parser.add_argument("--sendgrid-key", required=True, help="API key do SendGrid")
    parser.add_argument("--recipients", required=True, help="Lista de emails separada por vírgula")
    return parser.parse_args()


def main():
    args = parse_args()
    start_date = args.start
    end_date = args.end
    output_dir = args.output_dir
    os.makedirs(output_dir, exist_ok=True)

    base_name = f"{start_date}-{end_date}"
    pdf_path = os.path.join(output_dir, f"{base_name}.pdf")
    ofx_path = os.path.join(output_dir, f"{base_name}.ofx")

    token = get_bank_token(args.bank_creds)
    pdf_content = fetch_statement("pdf", start_date, end_date, token)
    ofx_content = fetch_statement("ofx", start_date, end_date, token)

    save_file(pdf_content, pdf_path)
    save_file(ofx_content, ofx_path)

    upload_to_drive(pdf_path, args.drive_creds)
    upload_to_drive(ofx_path, args.drive_creds)

    recipients = [email.strip() for email in args.recipients.split(",")]
    send_email([pdf_path, ofx_path], recipients, args.sendgrid_key,
               subject=f"Extrato {start_date} - {end_date}")


if __name__ == "__main__":
    main()
