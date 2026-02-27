#!/usr/bin/env bash
# TenderAI — Server provisioning script
# Usage: sudo ./setup.sh [domain]
# Example: sudo ./setup.sh tender.example.com

set -euo pipefail

DOMAIN="${1:-}"
INSTALL_DIR="/opt/tenderai"
SERVICE_USER="tenderai"

echo "=== TenderAI Server Setup ==="

# --- System packages ---
echo "[1/8] Installing system packages..."
apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip nginx certbot python3-certbot-nginx sqlite3

# --- Service user ---
echo "[2/8] Creating service user..."
if ! id "$SERVICE_USER" &>/dev/null; then
    useradd --system --shell /bin/false --home-dir "$INSTALL_DIR" "$SERVICE_USER"
fi

# --- Application directory ---
echo "[3/8] Setting up application directory..."
mkdir -p "$INSTALL_DIR"
cp -r . "$INSTALL_DIR/"
chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR"

# --- Python environment ---
echo "[4/8] Creating Python virtual environment..."
cd "$INSTALL_DIR"
python3 -m venv venv
source venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

# --- Data directories ---
echo "[5/8] Creating data directories..."
mkdir -p data/rfp_documents data/past_proposals data/vendor_quotes data/generated_proposals
mkdir -p data/knowledge_base/templates data/knowledge_base/standards data/knowledge_base/company_profile
mkdir -p db
chown -R "$SERVICE_USER:$SERVICE_USER" data db

# --- Environment file ---
echo "[6/8] Setting up environment..."
if [ ! -f .env ]; then
    cp .env.example .env
    # Generate a random API key
    MCP_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
    sed -i "s/change-me-to-a-secure-token/$MCP_KEY/" .env
    sed -i "s/TRANSPORT=stdio/TRANSPORT=http/" .env
    echo ""
    echo "  Generated MCP_API_KEY: $MCP_KEY"
    echo "  Edit $INSTALL_DIR/.env to set ANTHROPIC_API_KEY and other settings."
    echo ""
fi
chown "$SERVICE_USER:$SERVICE_USER" .env
chmod 600 .env

# --- Systemd service ---
echo "[7/8] Installing systemd service..."
cp systemd/tenderai.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable tenderai

# --- Nginx reverse proxy ---
echo "[8/8] Configuring nginx..."
if [ -n "$DOMAIN" ]; then
    sed "s/tender.yourdomain.com/$DOMAIN/g" nginx/tenderai.conf > /etc/nginx/sites-available/tenderai
    ln -sf /etc/nginx/sites-available/tenderai /etc/nginx/sites-enabled/
    rm -f /etc/nginx/sites-enabled/default
    nginx -t && systemctl reload nginx

    echo ""
    echo "  Obtaining SSL certificate for $DOMAIN..."
    certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --register-unsafely-without-email || {
        echo "  Warning: certbot failed. You may need to run it manually."
    }
fi

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Next steps:"
echo "  1. Edit $INSTALL_DIR/.env — set ANTHROPIC_API_KEY"
echo "  2. Start the service: systemctl start tenderai"
echo "  3. Check status: systemctl status tenderai"
echo "  4. View logs: journalctl -u tenderai -f"
if [ -n "$DOMAIN" ]; then
    echo "  5. Test: curl https://$DOMAIN/mcp"
fi
echo ""
