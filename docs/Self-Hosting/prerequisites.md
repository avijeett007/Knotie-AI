---
title: Prerequisites
description: List of prerequisites needed to set up and run Knotie-AI.
tags: Prerequisites, Setup, Knotie-AI, Docker, Python, Twilio
---

# 🛠️ Prerequisites

Before setting up Knotie-AI, ensure you have the following prerequisites:

- 🐳 **Docker**: Install Docker from [here](https://www.docker.com/get-started)
- 🐙 **Docker Compose**: Included with Docker Desktop
- ☎️ **Twilio Account**: [Signup here](https://www.twilio.com/login)
- 🧠 **ElevenLabs Account**: [Signup here](https://try.elevenlabs.io/434k6rx9zk3h)
- 💾 **Groq Account**: [Create keys here](https://console.groq.com/keys)
- 🌐 **OpenAI Account**: [Create keys here](https://platform.openai.com/account/usage)
- 🌍 **NGROK Account**: [Register here](https://ngrok.com/)

---

## 🛠️ Twilio Configuration

1. Once your Twilio account is registered, create a phone number [here](https://console.twilio.com/us1/develop/phone-numbers/manage/incoming). Twilio provides free credit and a free phone number to test. For production usage, make sure to buy a local number.

2. Run the following command to start NGROK:
   ```bash
   ngrok http 5000
   ```
   This will create a public link such as `https://a98d-82-26-133-9.ngrok-free.app`. Make a note of this URL.

3. Update this URL and API Keys/Account SID/Auth Tokens, etc., from Twilio, OpenAI, Eleven Labs into the `.env` file as described in the run steps below.

4. Go to the Twilio Manage Phone number page and update the following sections with the NGROK Public URL:
   ```bash
   This is a Must Step
   -------------------

   A Call Comes In --> https://ngrok_public_link/gather-inbound
   Primary Handler Fails --> https://ngrok_public_link/gather

   Click Save Changes
   ```

![Twilio Configuration](../../image.png)