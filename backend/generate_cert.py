"""
Phase 7: Generates a self-signed HTTPS certificate for local development.

Phone browsers (Chrome/Safari) block camera access (getUserMedia) on plain
HTTP unless the origin is localhost. Since the phone loads the page via the
laptop's LAN IP, we need HTTPS - even a self-signed one works fine for this,
the phone will just show a one-time "not secure, continue anyway" warning.

Usage:
    python backend/generate_cert.py
    python backend/generate_cert.py --ip 192.168.1.14   (override auto-detected IP)

Run this again if your laptop's IP address changes (e.g. after reconnecting
to a different Wi-Fi network).
"""

import argparse
import datetime
import ipaddress
import socket
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

CERT_DIR = Path(__file__).resolve().parent / "certs"


def detect_lan_ip() -> str:
    """Finds this machine's LAN IP the same way the OS would pick one for
    outbound traffic, without actually sending anything."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def generate_cert(ip: str):
    CERT_DIR.mkdir(parents=True, exist_ok=True)

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, ip),
    ])

    san_entries = [
        x509.DNSName("localhost"),
        x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
        x509.IPAddress(ipaddress.ip_address(ip)),
    ]

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.now(datetime.timezone.utc))
        .not_valid_after(datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=365))
        .add_extension(x509.SubjectAlternativeName(san_entries), critical=False)
        .sign(key, hashes.SHA256())
    )

    key_path = CERT_DIR / "key.pem"
    cert_path = CERT_DIR / "cert.pem"

    key_path.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))

    print(f"Generated self-signed certificate for IP: {ip}")
    print(f"  Cert: {cert_path}")
    print(f"  Key:  {key_path}")
    print(f"  Valid for 365 days")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ip", type=str, default=None, help="Override the auto-detected LAN IP")
    args = parser.parse_args()

    ip = args.ip or detect_lan_ip()
    generate_cert(ip)


if __name__ == "__main__":
    main()
