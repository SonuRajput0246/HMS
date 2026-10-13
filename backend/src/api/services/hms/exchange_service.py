from decimal import Decimal
import requests

class ExchangeService:

    @staticmethod
    def get_rate(from_currency: str, to_currency: str) -> Decimal:
        try:
            response = requests.get(
                f"https://api.exchangerate-api.com/v4/latest/{from_currency}",
                timeout=5
            )
            response.raise_for_status()

            data = response.json()
            rate = data["rates"].get(to_currency)

            if not rate:
                raise ValueError(f"Rate not found for {to_currency}")

            return Decimal(str(rate))

        except requests.RequestException as e:
            raise Exception(f"Exchange API failed: {str(e)}")