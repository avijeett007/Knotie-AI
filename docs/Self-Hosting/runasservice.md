---
title: Run The Code as Docker Container
description: Steps to set up Knotie-AI using Docker and configuring environment variables.
tags: Setup, Docker, Configuration, Knotie-AI
---

# ⚙️ Run Steps As Docker Service (For Business Owners/Entrepreneurs/Non-Dev Purpose/Checking Out Purpose)

## Steps to Run

1. 📥 **Clone the repository** or download the files to your local machine.
   ```bash
   git clone https://github.com/avijeett007/knotie-ai.git
   cd knotie-ai
   ```

2. 📂 **Navigate to the project directory** where `docker-compose-deploy.yml` is located.
   ```bash
   cd knotie-ai
   ```

3. 📝 **Copy `.env_sample` to `.env`** and modify the environment variables as per your requirements.
   ```bash
   cp .env_sample .env
   ```

4. 🛠️ **Run the following command to build and start the containers**:
   ```bash
   docker-compose -f docker-compose-deploy.yml up -d
   ```

5. 🌐 **Access the application** via `http://localhost:5000` or another configured port or if hosting on cloud, use http://<public-ip>:5000.

---

## 🛑 Stopping the Application

To stop the application, use the following Docker Compose command:

```bash
 docker-compose -f docker-compose-deploy.yml down
```

Next, Follow the [Configuration Guide](installation.md)