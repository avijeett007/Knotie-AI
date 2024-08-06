---
title: Testing
description: Instructions to test the AI Sales Agent using Postman or similar API execution platform.
tags: Testing, API, Postman, Knotie-AI
---

# 🧪 Testing Your AI Sales Agent

To test the agent, install Postman or a similar API execution platform. Open Postman and click on import and paste the below CURL command:

```bash
curl --location 'https://a98d-82-26-133-9.ngrok-free.app/start-call' --header 'Content-Type: application/json' --data '{
  "customer_name" : "Avijit",
  "customer_phonenumber": "+441234567890",
  "customer_businessdetails": "Looking for a gym membership to address back pain"
}'
```

Make sure to change the public URL with your NGROK provided URL and phone number/business details as per your testing requirement.