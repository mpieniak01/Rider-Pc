# Network Security Configuration Guide

## Overview

Ten dokument opisuje konfigurację bezpiecznego kanału sieciowego między Rider-PI a Klientem PC (środowisko WSL).

## Wybór Trybu

Klient PC używa zmiennej środowiskowej `SECURE_MODE` do określenia trybu połączenia:

```bash
# Tryb development (domyślnie)
SECURE_MODE=false

# Tryb production
SECURE_MODE=true
```

### Development Mode

W trybie development (`SECURE_MODE=false`), Klient PC łączy się z Rider-PI bez szyfrowania. Odpowiedni for:
- Rozwoju w sieci lokalnej
- Testowania i debugowania
- Scenariuszy gdzie Rider-PI jest w zaufanej sieci lokalnej

**Konfiguracja:**
```bash
# Plik .env
RIDER_PI_HOST=192.168.1.100
RIDER_PI_PORT=8080
SECURE_MODE=false
```

### Tryb Production

W trybie production (`SECURE_MODE=true`), Klient PC wymaga konfiguracji VPN or mTLS.

**Konfiguracja:**
```bash
# Plik .env
RIDER_PI_HOST=10.0.0.1  # or IP VPN
RIDER_PI_PORT=8443      # Port HTTPS for mTLS
SECURE_MODE=true
MTLS_CERT_PATH=/path/to/client-cert.pem
MTLS_KEY_PATH=/path/to/client-key.pem
MTLS_CA_PATH=/path/to/ca-cert.pem
```

## Opcja 1: Development Mode (Sieć Lokalna)

Dla rozwoju i testowania w sieci lokalnej:

1. Make sure że Rider-PI jest dostępny w sieci lokalnej
2. Configure `.env`:
   ```bash
   RIDER_PI_HOST=192.168.1.100  # Twój IP Rider-PI
   RIDER_PI_PORT=8080
   SECURE_MODE=false
   ```
3. Uruchom Klienta PC:
   ```bash
   python -m pc_client.main
   ```

## Opcja 2: Tryb Production - WireGuard VPN (Recommended)

WireGuard to lekki, nowoczesny protokół VPN zapewniający bezpieczną komunikację z minimalnym narzutem.

### Instalacja

#### Na Rider-PI (Debian/Raspbian)
```bash
sudo apt update
sudo apt install wireguard wireguard-tools
```

#### Na PC (WSL Debian)
```bash
sudo apt update
sudo apt install wireguard wireguard-tools
```

### Konfiguracja

#### 1. Wygeneruj Klucze

**Na Rider-PI:**
```bash
cd /etc/wireguard
umask 077
wg genkey | tee privatekey | wg pubkey > publickey
```

**Na PC (WSL):**
```bash
sudo mkdir -p /etc/wireguard
cd /etc/wireguard
sudo umask 077
wg genkey | sudo tee privatekey | wg pubkey | sudo tee publickey
```

#### 2. Configure Rider-PI jako Serwer

Utwórz `/etc/wireguard/wg0.conf` na Rider-PI:

```ini
[Interface]
PrivateKey = <RIDER_PI_PRIVATE_KEY>
Address = 10.0.0.1/24
ListenPort = 51820

# PC Client
[Peer]
PublicKey = <PC_PUBLIC_KEY>
AllowedIPs = 10.0.0.2/32
```

#### 3. Configure PC jako Klienta

Utwórz `/etc/wireguard/wg0.conf` na PC:

```ini
[Interface]
PrivateKey = <PC_PRIVATE_KEY>
Address = 10.0.0.2/24

[Peer]
PublicKey = <RIDER_PI_PUBLIC_KEY>
Endpoint = <RIDER_PI_PUBLIC_IP>:51820
AllowedIPs = 10.0.0.0/24
PersistentKeepalive = 25
```

#### 4. Uruchom WireGuard

**Na Rider-PI:**
```bash
sudo systemctl enable wg-quick@wg0
sudo systemctl start wg-quick@wg0
```

**Na PC:**
```bash
sudo systemctl enable wg-quick@wg0
sudo systemctl start wg-quick@wg0
```

#### 5. Weryfikuj Połączenie

```bash
# Z PC do Rider-PI
ping 10.0.0.1

# Z Rider-PI do PC
ping 10.0.0.2
```

### Konfiguracja Klienta PC for VPN

Zaktualizuj `.env`:
```bash
RIDER_PI_HOST=10.0.0.1  # IP VPN Rider-PI
RIDER_PI_PORT=8080
SECURE_MODE=false  # VPN zapewnia szyfrowanie
```

## Opcja 3: Mutual TLS (mTLS)

For environments requiring mutual authentication certyfikatów.

### 1. Wygeneruj Certyfikaty

```bash
# Utwórz CA
openssl genrsa -out ca-key.pem 4096
openssl req -new -x509 -days 365 -key ca-key.pem -out ca-cert.pem

# Certyfikat serwera (Rider-PI)
openssl genrsa -out server-key.pem 4096
openssl req -new -key server-key.pem -out server.csr
openssl x509 -req -days 365 -in server.csr -CA ca-cert.pem -CAkey ca-key.pem -CAcreateserial -out server-cert.pem

# Certyfikat klienta (PC)
openssl genrsa -out client-key.pem 4096
openssl req -new -key client-key.pem -out client.csr
openssl x509 -req -days 365 -in client.csr -CA ca-cert.pem -CAkey ca-key.pem -CAcreateserial -out client-cert.pem
```

### 2. Konfiguruj Rider-PI

```python
# W API server używaj certyfikatów SSL
uvicorn.run(
    app,
    host="0.0.0.0",
    port=8443,
    ssl_keyfile="server-key.pem",
    ssl_certfile="server-cert.pem",
    ssl_ca_certs="ca-cert.pem",
    ssl_cert_reqs=ssl.CERT_REQUIRED
)
```

### 3. Konfiguruj Klienta PC

```bash
# .env
RIDER_PI_HOST=192.168.1.100
RIDER_PI_PORT=8443
SECURE_MODE=true
MTLS_CERT_PATH=/path/to/client-cert.pem
MTLS_KEY_PATH=/path/to/client-key.pem
MTLS_CA_PATH=/path/to/ca-cert.pem
```

## Konfiguracja Firewall

### Na Rider-PI

```bash
# UFW
sudo ufw allow 51820/udp  # WireGuard
sudo ufw allow from 10.0.0.0/24 to any port 8080  # REST API
sudo ufw allow from 10.0.0.0/24 to any port 5555:5556  # ZMQ
sudo ufw enable
```

### Na PC (WSL)

WSL2 używa Windows Firewall. Configure w Windows:
```powershell
# PowerShell jako Administrator
New-NetFirewallRule -DisplayName "WireGuard" -Direction Inbound -Protocol UDP -LocalPort 51820 -Action Allow
```

## Automatyczny Start

### Rider-PI (systemd)

```ini
# /etc/systemd/system/wg-quick@wg0.service już istnieje
sudo systemctl enable wg-quick@wg0
```

### PC (WSL)

Utwórz `/etc/wsl.conf`:
```ini
[boot]
command = "systemctl start wg-quick@wg0"
```

## Monitorowanie i Rozwiązywanie Problemów

### Check Status WireGuard

```bash
sudo wg show
```

### Test Łączność

```bash
# Ping przez VPN
ping 10.0.0.1

# Test REST API
curl http://10.0.0.1:8080/healthz

# Check porty
ss -tulnp | grep 51820
```

### Powszechne Problemy

**WireGuard nie łączy się:**
- Check klucze publiczne w konfiguracji
- Weryfikuj Endpoint IP i port
- Check reguły firewall
- Check routing: `ip route`

**mTLS handshake fails:**
- Weryfikuj ścieżki certyfikatów
- Check daty ważności certyfikatów: `openssl x509 -in cert.pem -noout -dates`
- Check uprawnienia plików (600 for kluczy prywatnych)

---

**Status**: Gotowe do Produkcji ✅  
**Recommended**: WireGuard VPN for produkcji  
**Data**: 2025-11-12
