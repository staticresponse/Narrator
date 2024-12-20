$timestamp = Get-Date -Format "yyyyMMdd"

docker rm -f tts-generator
# Build the Docker image with a timestamped tag
docker build -t tts-generator:$timestamp .

# Define a directory on the host to persist the data
$hostDir = pwd

# Create the host directory if it doesn't exist
if (!(Test-Path -Path $hostDir)) {
    New-Item -ItemType Directory -Path $hostDir
}

# Run the Docker container using the timestamped image and map the volume
docker run -d -p 5000:5000 --name tts-generator `
    -v "${hostDir}:/app" `
    tts-generator:$timestamp
