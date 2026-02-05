# contoso-payments-api

Payment processing service for Contoso e-commerce platform.

## Running

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## API

- `GET /` - Service info
- `POST /payments/authorize` - Authorize payment
- `POST /payments/{id}/capture` - Capture payment
- `POST /payments/{id}/refund` - Refund payment
