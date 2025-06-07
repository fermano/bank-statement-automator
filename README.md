# Bank Statement Automator

Este projeto fornece um script em Python para automatizar o download de extratos do Banco Inter, gerar arquivos nos formatos PDF e OFX, enviar os arquivos para o Google Drive e encaminhá-los por e-mail utilizando o SendGrid.

## Pré-requisitos

- Python 3.8 ou superior
- Instalar as dependências do arquivo `requirements.txt`:

```bash
pip install -r requirements.txt
```

## Uso

```bash
python bank_statement_automator.py \
  --de YYYY-MM-DD \
  --ate YYYY-MM-DD \
  --output-dir ./saida \
  --bank-creds caminho/credenciais_banco.json \
  --drive-creds <ARQUIVO_CREDENCIAIS_DRIVE> \
  --sendgrid-key <API_KEY_SENDGRID> \
  --recipients email1@example.com,email2@example.com
```

- **--de** e **--ate** representam o período desejado do extrato.
- **--output-dir** define o diretório onde os arquivos serão salvos.
- **--bank-creds** caminho para um arquivo JSON com `client_id`, `client_secret`, `cert` e `key` do Banco Inter.
- **--drive-creds** deve apontar para o arquivo de credenciais do Google Drive.
- **--sendgrid-key** é a chave da API do SendGrid para envio de e-mails.
- **--recipients** lista de e-mails de destino separada por vírgula.

Os arquivos gerados seguirão o padrão `<data de>-<data até>.pdf` e `<data de>-<data até>.ofx`.

### Arquivo de credenciais do Banco Inter

Crie um JSON com as credenciais de API do banco:

```json
{
  "client_id": "<seu_client_id>",
  "client_secret": "<seu_client_secret>",
  "cert": "/caminho/certificado.crt",
  "key": "/caminho/chave.key"
}
```

O caminho para esse arquivo deve ser passado no parâmetro `--bank-creds`.

## Observações

- As chamadas de API para o Banco Inter estão representadas com placeholders e devem ser ajustadas conforme a documentação oficial do banco.
- É necessário configurar corretamente as credenciais do Google Drive e do SendGrid para que o envio funcione.
