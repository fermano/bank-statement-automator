import argparse
import os
import base64
import json
import requests
from typing import List, Dict
from uuid import uuid4
from datetime import date


def load_bank_credentials(path: str) -> Dict[str, str]:
    """Load Banco Inter credentials from a JSON file."""
    with open(path) as f:
        return json.load(f)

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


def fetch_pdf(start_date: str, end_date: str, token: str, creds: Dict[str, str]) -> bytes:
    """Retrieve PDF statement from Banco Inter."""
    url = "https://cdpj.partners.bancointer.com.br/banking/v2/extrato/exportar"
    headers = {
        "Authorization": f"Bearer {token}",
        "x-conta-corrente": creds["account"],
        "Content-Type": "Application/json",
    }
    params = {"dataInicio": start_date, "dataFim": end_date}
    response = requests.get(
        url,
        params=params,
        headers=headers,
        cert=(creds["cert"], creds["key"]),
    )
    response.raise_for_status()
    data = response.json()
    pdf_b64 = data.get("pdf") if isinstance(data, dict) else None
    if not pdf_b64:
        # Fallback to raw content if response is already PDF bytes
        return response.content
    return base64.b64decode(pdf_b64)


def fetch_transactions(start_date: str, end_date: str, token: str, creds: Dict[str, str]):
    """Retrieve transaction list from Banco Inter."""
    url = "https://cdpj.partners.bancointer.com.br/banking/v2/extrato"
    headers = {
        "Authorization": f"Bearer {token}",
        "x-conta-corrente": creds["account"],
        "Content-Type": "Application/json",
    }
    params = {"dataInicio": start_date, "dataFim": end_date}
    response = requests.get(
        url,
        params=params,
        headers=headers,
        cert=(creds["cert"], creds["key"]),
    )
    response.raise_for_status()
    data = response.json()
    # The API returns an object with a "transacoes" field containing the list
    # of transactions. The OFX generator expects to receive this list directly.
    return data.get("transacoes", data)


def fetch_balance(end_date: str, token: str, creds: Dict[str, str]):
    """Retrieve account balance from Banco Inter."""
    url = "https://cdpj.partners.bancointer.com.br/banking/v2/saldo"
    headers = {
        "Authorization": f"Bearer {token}",
        "x-conta-corrente": creds["account"],
        "Content-Type": "Application/json",
    }
    params = {"dataSaldo": end_date}
    response = requests.get(
        url,
        params=params,
        headers=headers,
        cert=(creds["cert"], creds["key"]),
    )
    response.raise_for_status()
    return response.json()


def generate_ofx(transactions, saldo, start_date: str, end_date: str) -> bytes:
    """Generate an OFX file from transactions and balance info."""
    lines = [
        "OFXHEADER:100",
        "DATA:OFXSGML",
        "VERSION:102",
        "SECURITY:NONE",
        "ENCODING:USASCII",
        "CHARSET:1252",
        "COMPRESSION:NONE",
        "OLDFILEUID:NONE",
        "NEWFILEUID:NONE",
        "",
        "<OFX>",
        "<SIGNONMSGSRSV1>",
        "<SONRS>",
        "<STATUS>",
        "<CODE>0</CODE>",
        "<SEVERITY>INFO</SEVERITY>",
        "</STATUS>",
        f"<DTSERVER>{date.today().strftime('%Y%m%d')}</DTSERVER>",
        "<LANGUAGE>POR</LANGUAGE>",
        "<FI>",
        "<ORG>Banco Intermedium S/A</ORG>",
        "<FID>077</FID>",
        "</FI>",
        "</SONRS>",
        "</SIGNONMSGSRSV1>",
        "<BANKMSGSRSV1>",
        "<STMTTRNRS>",
        "<TRNUID>1001</TRNUID>",
        "<STATUS>",
        "<CODE>0</CODE>",
        "<SEVERITY>INFO</SEVERITY>",
        "</STATUS>",
        "<STMTRS>",
        "<CURDEF>BRL</CURDEF>",
        "<BANKACCTFROM>",
        "<BANKID>077</BANKID>",
        "<BRANCHID>0001-9</BRANCHID>",
        "<ACCTID>94401993</ACCTID>",
        "<ACCTTYPE>CHECKING</ACCTTYPE>",
        "</BANKACCTFROM>",
        "<BANKTRANLIST>",
        f"<DTSTART>{start_date.replace('-', '')}</DTSTART>",
        f"<DTEND>{end_date.replace('-', '')}</DTEND>",
    ]

    for tr in transactions:
        tipo = "CREDIT" if tr.get("tipoOperacao") == "C" else "PAYMENT"
        dt = tr.get("dataEntrada", "").replace("-", "")
        valor = tr.get("valor", 0)
        desc = tr.get("descricao", "")
        lines.extend([
            "<STMTTRN>",
            f"<TRNTYPE>{tipo}</TRNTYPE>",
            f"<DTPOSTED>{dt}</DTPOSTED>",
            f"<TRNAMT>{'-' if tipo == 'PAYMENT' else ''}{valor}</TRNAMT>",
            f"<FITID>{uuid4().hex}</FITID>",
            "<CHECKNUM>077</CHECKNUM>",
            "<REFNUM>077</REFNUM>",
            f"<MEMO>{desc}</MEMO>",
            "</STMTTRN>",
        ])

    lines.extend([
        "</BANKTRANLIST>",
        "<LEDGERBAL>",
        f"<BALAMT>{saldo.get('disponivel')}</BALAMT>",
        f"<DTASOF>{date.today().strftime('%Y%m%d')}</DTASOF>",
        "</LEDGERBAL>",
        "</STMTRS>",
        "</STMTTRNRS>",
        "</BANKMSGSRSV1>",
        "</OFX>",
    ])

    return "\n".join(lines).encode("utf-8")


def save_file(content: bytes, path: str):
    with open(path, "wb") as f:
        f.write(content)
    print(f"Saved file {path}")


DEFAULT_DRIVE_FOLDER_ID = "15IK2XcKpNAwH5vd7a05sTyZ0CTPzacLu"


def upload_to_drive(
    filepath: str,
    drive_credentials: str,
    folder_id: str = DEFAULT_DRIVE_FOLDER_ID,
) -> str:
    if GoogleAuth is None:
        raise RuntimeError("pydrive2 is required for Google Drive uploads")
    gauth = GoogleAuth()
    # Use service account credentials JSON for authentication
    if hasattr(gauth, "ServiceAccountAuth"):
        gauth.ServiceAccountAuth(drive_credentials)
    else:
        from oauth2client.service_account import ServiceAccountCredentials
        scopes = ["https://www.googleapis.com/auth/drive.file"]
        gauth.credentials = ServiceAccountCredentials.from_json_keyfile_name(
            drive_credentials, scopes=scopes
        )
        gauth.auth_method = "service"
    drive = GoogleDrive(gauth)
    file_drive = drive.CreateFile({
        "title": os.path.basename(filepath),
        "parents": [{"id": folder_id}],
    })
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


def get_bank_token(creds: Dict[str, str]) -> str:
    """Retrieve an OAuth token from Banco Inter using loaded credentials."""

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
    parser.add_argument("--inicio", required=True, help="Data inicio (YYYY-MM-DD)")
    parser.add_argument("--fim", required=True, help="Data fim (YYYY-MM-DD)")
    parser.add_argument("--output-dir", default="./output", help="Diretório para salvar arquivos")
    parser.add_argument(
        "--bank-creds",
        required=True,
        help=(
            "Arquivo JSON com client_id, client_secret, cert, key e account do "
            "Banco Inter"
        ),
    )
    parser.add_argument("--drive-creds", required=True, help="Credenciais do Google Drive")
    parser.add_argument(
        "--drive-folder-id",
        default=DEFAULT_DRIVE_FOLDER_ID,
        help="ID da pasta do Google Drive para upload",
    )
    parser.add_argument("--sendgrid-key", required=True, help="API key do SendGrid")
    parser.add_argument("--recipients", required=True, help="Lista de emails separada por vírgula")
    return parser.parse_args()


def main():
    args = parse_args()
    start_date = args.inicio
    end_date = args.fim
    output_dir = args.output_dir
    os.makedirs(output_dir, exist_ok=True)

    base_name = f"{start_date}-{end_date}"
    pdf_path = os.path.join(output_dir, f"{base_name}.pdf")
    ofx_path = os.path.join(output_dir, f"{base_name}.ofx")

    bank_creds = load_bank_credentials(args.bank_creds)
    token = get_bank_token(bank_creds)
    pdf_content = fetch_pdf(start_date, end_date, token, bank_creds)
    transactions = fetch_transactions(start_date, end_date, token, bank_creds)
    saldo = fetch_balance(end_date, token, bank_creds)
    ofx_content = generate_ofx(transactions, saldo, start_date, end_date)

    save_file(pdf_content, pdf_path)
    save_file(ofx_content, ofx_path)

    upload_to_drive(pdf_path, args.drive_creds, args.drive_folder_id)
    upload_to_drive(ofx_path, args.drive_creds, args.drive_folder_id)

    recipients = [email.strip() for email in args.recipients.split(",")]
    send_email([pdf_path, ofx_path], recipients, args.sendgrid_key,
               subject=f"Extrato {start_date} - {end_date}")


if __name__ == "__main__":
    main()
