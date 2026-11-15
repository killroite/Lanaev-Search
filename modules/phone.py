import phonenumbers
from phonenumbers import geocoder, carrier

def analyze_phone(raw: str) -> dict:
    result = {"input": raw, "valid": False, "region": None,
              "carrier": None, "e164": None, "national": None}
    try:
        num = phonenumbers.parse(raw, None)
    except Exception:
        return result
    if not phonenumbers.is_valid_number(num):
        return result
    result["valid"] = True
    result["e164"] = phonenumbers.format_number(num, phonenumbers.PhoneNumberFormat.E164)
    result["national"] = phonenumbers.format_number(num, phonenumbers.PhoneNumberFormat.NATIONAL)
    result["region"] = geocoder.description_for_number(num, "ru") or "—"
    result["carrier"] = carrier.name_for_number(num, "ru") or "—"
    return result
