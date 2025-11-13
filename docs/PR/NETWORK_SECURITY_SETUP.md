# Network Security Setup Guide

## Overview

This document describes the secure network channel setup between Rider-PI and the PC Client (WSL environment).

## Option 1: WireGuard VPN (Recommended)

WireGuard is a lightweight, modern VPN protocol that provides secure communication with minimal overhead.

### Installation

#### On Rider-PI (Debian/Raspbian)
```bash
sudo apt update
sudo apt install wireguard wireguard-tools
```

#### On PC (WSL Debian)
```bash
sudo apt update
sudo apt install wireguard wireguard-tools
```

### Configuration

#### Generate Keys

On both Rider-PI and PC:
```bash
# Generate private and public keys
wg genkey | tee privatekey | wg pubkey > publickey
```

#### Rider-PI Configuration
Create `/etc/wireguard/wg0.conf`:
```ini
[Interface]
Address = 10.0.0.1/24
PrivateKey = <rider-pi-private-key>
ListenPort = 51820

[Peer]
PublicKey = <pc-public-key>
AllowedIPs = 10.0.0.2/32
```

#### PC Configuration
Create `/etc/wireguard/wg0.conf`:
```ini
[Interface]
Address = 10.0.0.2/24
PrivateKey = <pc-private-key>

[Peer]
PublicKey = <rider-pi-public-key>
Endpoint = <rider-pi-lan-ip>:51820
AllowedIPs = 10.0.0.1/32
PersistentKeepalive = 25
```

#### Start WireGuard

On both systems:
```bash
sudo wg-quick up wg0
# Enable on boot
sudo systemctl enable wg-quick@wg0
```

### Update PC Client Configuration

Update `.env` to use VPN addresses:
```bash
RIDER_PI_HOST=10.0.0.1
```

## Option 2: mTLS (Mutual TLS)

For scenarios where VPN is not feasible, use mutual TLS authentication.

### Generate Certificates

```bash
# Generate CA
openssl req -x509 -newkey rsa:4096 -days 365 -nodes \
  -keyout ca-key.pem -out ca-cert.pem \
  -subj "/CN=Rider-CA"

# Generate Server Certificate (Rider-PI)
openssl req -newkey rsa:4096 -nodes \
  -keyout server-key.pem -out server-req.pem \
  -subj "/CN=rider-pi"

openssl x509 -req -in server-req.pem -days 365 \
  -CA ca-cert.pem -CAkey ca-key.pem -CAcreateserial \
  -out server-cert.pem

# Generate Client Certificate (PC)
openssl req -newkey rsa:4096 -nodes \
  -keyout client-key.pem -out client-req.pem \
  -subj "/CN=pc-client"

openssl x509 -req -in client-req.pem -days 365 \
  -CA ca-cert.pem -CAkey ca-key.pem -CAcreateserial \
  -out client-cert.pem
```

### Nginx Configuration (Rider-PI)

```nginx
server {
    listen 8443 ssl;
    
    ssl_certificate /etc/ssl/certs/server-cert.pem;
    ssl_certificate_key /etc/ssl/private/server-key.pem;
    ssl_client_certificate /etc/ssl/certs/ca-cert.pem;
    ssl_verify_client on;
    
    location / {
        proxy_pass http://localhost:8080;
    }
}
```

### PC Client Configuration

Update the REST adapter to use client certificates:
```python
client = httpx.AsyncClient(
    cert=("client-cert.pem", "client-key.pem"),
    verify="ca-cert.pem"
)
```

## IP Addressing Plan

### VPN Network
- Network: `10.0.0.0/24`
- Rider-PI: `10.0.0.1`
- PC Client: `10.0.0.2`
- Gateway: `10.0.0.1`

### Service Ports
- REST API: `8080` (HTTP) or `8443` (HTTPS/mTLS)
- ZMQ PUB: `5555`
- ZMQ SUB: `5556`
- Task Queue: `5672` (RabbitMQ) or `6379` (Redis)
- Prometheus: `9090`
- Node Exporter: `9100`

## Firewall Configuration

### Rider-PI (UFW)
```bash
# Allow SSH
sudo ufw allow 22/tcp

# Allow WireGuard
sudo ufw allow 51820/udp

# Allow services from VPN network only
sudo ufw allow from 10.0.0.0/24 to any port 8080
sudo ufw allow from 10.0.0.0/24 to any port 5555
sudo ufw allow from 10.0.0.0/24 to any port 5556

# Enable firewall
sudo ufw enable
```

### PC (WSL - iptables)
```bash
# Allow established connections
sudo iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT

# Allow WireGuard
sudo iptables -A INPUT -p udp --dport 51820 -j ACCEPT

# Allow VPN traffic
sudo iptables -A INPUT -s 10.0.0.0/24 -j ACCEPT

# Drop everything else
sudo iptables -A INPUT -j DROP
```

### Windows Firewall
Add inbound rules for:
- UDP port 51820 (WireGuard)
- Allow WSL network adapter

## Security Best Practices

### Key Management
1. Store private keys with restricted permissions:
   ```bash
   chmod 600 /etc/wireguard/privatekey
   chmod 600 /etc/ssl/private/*.pem
   ```

2. Never commit keys to version control

3. Use a secrets manager for production:
   - HashiCorp Vault
   - Azure Key Vault
   - AWS Secrets Manager

### Certificate Rotation
- Rotate certificates every 90 days
- Automate with scripts or use ACME protocol
- Maintain certificate expiry monitoring

### Connection Monitoring
- Monitor active VPN connections: `sudo wg show`
- Check TLS handshake logs
- Set up alerts for failed authentication attempts

## Automated Startup

### Windows (PowerShell Script)
Create `start-vpn.ps1`:
```powershell
# Start WSL
wsl -d Debian -u root -- wg-quick up wg0

# Wait for connection
Start-Sleep -Seconds 5

# Verify connection
wsl -d Debian -- ping -c 3 10.0.0.1
```

Add to Task Scheduler to run at startup.

### WSL (systemd)
```bash
sudo systemctl enable wg-quick@wg0
```

## Troubleshooting

### Connection Issues
```bash
# Check WireGuard status
sudo wg show

# Check if interface is up
ip addr show wg0

# Ping test
ping 10.0.0.1

# Check firewall
sudo ufw status verbose
sudo iptables -L -v -n
```

### Certificate Issues
```bash
# Verify certificate
openssl x509 -in cert.pem -text -noout

# Test TLS connection
openssl s_client -connect rider-pi:8443 \
  -cert client-cert.pem -key client-key.pem \
  -CAfile ca-cert.pem
```

## Performance Considerations

### WireGuard
- Low overhead (~4-5% CPU)
- High throughput (near line speed)
- Low latency (~1-2ms added)

### mTLS
- Higher overhead (~10-15% CPU)
- Certificate validation on each request
- Consider connection pooling

## References

- [WireGuard Official Documentation](https://www.wireguard.com/)
- [OpenSSL Certificate Management](https://www.openssl.org/docs/)
- [UFW Firewall Guide](https://help.ubuntu.com/community/UFW)
