#!/usr/bin/env bash
set -e

# Generate a secure token
API_TOKEN="$(openssl rand -hex 16)"
echo "🔑 API token generated: ${API_TOKEN}"

# Get the local IP of the device (for API endpoint)
DEVICE_IP=$(hostname -I | awk '{print $1}')
API_ENDPOINT="http://${DEVICE_IP}:8030"

# Detect GPUs via nvidia-smi
if command -v nvidia-smi &>/dev/null; then
  # Query GPU details (name, memory, SM clock, mem clock, power draw)
  GPU_INFO=$(nvidia-smi \
    --query-gpu=index,name,memory.total,clocks.sm,clocks.mem,power.draw \
    --format=csv,noheader,nounits)
else
  GPU_INFO=""
fi

# Parse into arrays
declare -a GPU_LINES=()
while IFS= read -r line; do GPU_LINES+=("$line"); done <<< "$GPU_INFO"

GPU_COUNT=${#GPU_LINES[@]}
echo "🎮 GPUs detected: $GPU_COUNT"

# If there are no GPUs detected, exit early
if [[ $GPU_COUNT -eq 0 ]]; then
  echo "No GPUs detected."
  exit 1
fi

# Variables to track the most powerful GPU
MAX_FLOPS=0
MOST_POWERFUL_GPU=""

# For each GPU, compute FLOPS and find the most powerful one
for line in "${GPU_LINES[@]}"; do
  IFS=',' read -r idx name mem_sm sm_clk mem_clk power <<< "$line"

  # Estimate FLOPS: FLOPS = sm_clock(GHz) * cores_per_sm * num_sm * 2 (GFLOPS)
  FLOPS=$(awk -v clk="$sm_clk" 'BEGIN {print clk * 128 * 2}')

  # Track the GPU with the maximum FLOPS
  if (( $(echo "$FLOPS > $MAX_FLOPS" | bc -l) )); then
    MAX_FLOPS=$FLOPS
    MOST_POWERFUL_GPU="$line"
  fi
done

# Extract information of the most powerful GPU
IFS=',' read -r idx name mem_sm sm_clk mem_clk power <<< "$MOST_POWERFUL_GPU"
FLOPS=$(awk -v clk="$sm_clk" 'BEGIN {print clk * 128 * 2}')
GPU_UUID=$(uuidgen)

# Prepare JSON payload to send to platform API
JSON_PAYLOAD=$(jq -n \
  --arg uuid "$GPU_UUID" \
  --arg token "$API_TOKEN" \
  --arg name "$name" \
  --arg flops "$(printf "%.1f" "$(awk -v f="$FLOPS" 'BEGIN {print f/1e3}')")" \
  --arg power "$power" \
  --arg endpoint "$API_ENDPOINT" \
  '{
    uuid: $uuid,
    token: $token,
    name: $name,
    flops: $flops,
    power: $power,
    api_endpoint: $endpoint
  }')

# Submit the data to your platform
curl -X POST $API_ENDPOINT \
  -H "Authorization: Bearer ${API_TOKEN}" \
  -H "Content-Type: application/json" \
  -d "$JSON_PAYLOAD"

# Install Docker + NVIDIA runtime
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg lsb-release
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
  sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) \
  signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] \
  https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io

# Install NVIDIA runtime
distribution=$(. /etc/os-release; echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list \
  | sudo tee /etc/apt/sources.list.d/nvidia-docker.list
sudo apt-get update
sudo apt-get install -y nvidia-docker2
sudo systemctl restart docker

# Install Backend.AI Agent
python3 -m pip install --user backend.ai-agent

# Write config
mkdir -p ~/.bai
cat > ~/.bai/config.toml << EOF
[agent]
mode = "standalone"

[docker]
runtime = "nvidia"

[server]
listen_ip = "0.0.0.0"
listen_port = 8030

[auth]
token = "${API_TOKEN}"
EOF

# Create systemd unit
sudo tee /etc/systemd/system/backend-ai-agent.service > /dev/null << EOF
[Unit]
Description=Backend.AI Agent (GPU)
After=docker.service

[Service]
Type=simple
User=$USER
Environment="PATH=/home/$USER/.local/bin:/usr/bin:/bin"
ExecStart=/home/$USER/.local/bin/bai-agent run
Restart=always

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable backend-ai-agent
sudo systemctl start backend-ai-agent

# At the end, print only the UUID for user to copy
echo ""
echo "✅ Setup complete!"
echo "• Copy this UUID into the registration page: $GPU_UUID"
