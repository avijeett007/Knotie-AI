---
title: Setup
description: Steps to set up Knotie-AI using Docker and configuring environment variables.
tags: Setup, Docker, Configuration, Knotie-AI
---

# ⚙️ Setup

## Steps to Run

1. 📥 **Clone the repository** or download the files to your local machine.
   ```bash
   git clone https://github.com/your-repo/knotie-ai.git
   cd knotie-ai
   ```

2. 📂 **Navigate to the project directory** where `docker-compose.yml` is located.
   ```bash
   cd knotie-ai
   ```

3. 📝 **Copy `.env_sample` to `.env`** and modify the environment variables as per your requirements.
   ```bash
   cp .env_sample .env
   ```

4. 🛠️ **Run the following command to build and start the containers**:
   ```bash
   docker-compose up --build
   ```

5. 🌐 **Access the application** via `http://localhost:5000` or another configured port.

---

## 🛑 Stopping the Application

To stop the application, use the following Docker Compose command:

```bash
docker-compose down
```

## 🔄 Changing Underlying Code

If you've changed any code in the application, please make sure to use the following Docker Compose command to rebuild the image and start it:

```bash
docker-compose build --no-cache
docker-compose up
```