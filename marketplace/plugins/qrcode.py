import qrcode
import io
import base64
import os

OUTIL = {
    "name": "qrcode",
    "description": "Générateur de QR codes (texte, URL, WiFi, vCard, etc.)",
    "parameters": {
        "type": "object",
        "properties": {
            "data": {"type": "string", "description": "Données à encoder (texte, URL, etc.)"},
            "type": {"type": "string", "description": "Type: text, url, wifi, vcard, email, sms, tel", "default": "text"},
            "size": {"type": "integer", "description": "Taille en pixels (box_size)", "default": 10},
            "border": {"type": "integer", "description": "Bordure (modules)", "default": 4},
            "error_correction": {"type": "string", "description": "Correction d'erreur: L, M, Q, H", "default": "M"},
            "output": {"type": "string", "description": "Fichier de sortie (PNG), ou 'base64' pour data URI", "default": "qrcode.png"}
        },
        "required": ["data"]
    }
}

DANGEREUX = False

EC_LEVELS = {"L": qrcode.constants.ERROR_CORRECT_L, "M": qrcode.constants.ERROR_CORRECT_M,
             "Q": qrcode.constants.ERROR_CORRECT_Q, "H": qrcode.constants.ERROR_CORRECT_H}

def format_wifi(ssid, password, security="WPA", hidden=False):
    return f"WIFI:T:{security};S:{ssid};P:{password};H:{'true' if hidden else 'false'};;"

def format_vcard(name, phone="", email="", org="", url="", address=""):
    lines = ["BEGIN:VCARD", "VERSION:3.0", f"FN:{name}"]
    if phone: lines.append(f"TEL:{phone}")
    if email: lines.append(f"EMAIL:{email}")
    if org: lines.append(f"ORG:{org}")
    if url: lines.append(f"URL:{url}")
    if address: lines.append(f"ADR:{address}")
    lines.append("END:VCARD")
    return "\n".join(lines)

def format_email(to, subject="", body=""):
    return f"mailto:{to}?subject={subject}&body={body}"

def format_sms(phone, body=""):
    return f"smsto:{phone}:{body}"

def format_tel(phone):
    return f"tel:{phone}"

def executer(args, config):
    data = args.get("data", "")
    qr_type = args.get("type", "text")
    size = args.get("size", 10)
    border = args.get("border", 4)
    ec = args.get("error_correction", "M").upper()
    output = args.get("output", "qrcode.png")
    
    if not data:
        return "Erreur: data requis"
    
    # Formater selon le type
    if qr_type == "wifi":
        # data format: "ssid|password|security|hidden"
        parts = data.split("|")
        data = format_wifi(parts[0], parts[1] if len(parts) > 1 else "", 
                          parts[2] if len(parts) > 2 else "WPA",
                          parts[3].lower() == "true" if len(parts) > 3 else False)
    elif qr_type == "vcard":
        # data format: "name|phone|email|org|url|address"
        parts = data.split("|")
        data = format_vcard(parts[0], parts[1] if len(parts) > 1 else "",
                           parts[2] if len(parts) > 2 else "",
                           parts[3] if len(parts) > 3 else "",
                           parts[4] if len(parts) > 4 else "",
                           parts[5] if len(parts) > 5 else "")
    elif qr_type == "email":
        # data format: "to|subject|body"
        parts = data.split("|")
        data = format_email(parts[0], parts[1] if len(parts) > 1 else "",
                           parts[2] if len(parts) > 2 else "")
    elif qr_type == "sms":
        # data format: "phone|body"
        parts = data.split("|")
        data = format_sms(parts[0], parts[1] if len(parts) > 1 else "")
    elif qr_type == "tel":
        data = format_tel(data)
    elif qr_type == "url" and not data.startswith(("http://", "https://")):
        data = "https://" + data
    
    # Générer le QR code
    qr = qrcode.QRCode(
        version=None,
        error_correction=EC_LEVELS.get(ec, qrcode.constants.ERROR_CORRECT_M),
        box_size=size,
        border=border
    )
    qr.add_data(data)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    if output == "base64":
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode()
        return f"data:image/png;base64,{b64}"
    
    # Sauvegarder
    output_dir = os.path.dirname(output)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    img.save(output)
    return f"QR code généré: {output} ({img.size[0]}x{img.size[1]}px)\nType: {qr_type}\nDonnées: {data[:80]}{'...' if len(data) > 80 else ''}"