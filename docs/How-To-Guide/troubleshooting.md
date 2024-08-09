---
title: 🛠️ Troubleshooting
description: This documentation will help you troubleshoot issues with Knotie-AI.
tags: Troubleshooting, Docker, Knotie-AI, Debugging
---

# 🛠️ Troubleshooting

If you encounter any issues while running Knotie-AI, this guide will help you diagnose and resolve them.

---

## 🔍 Basic Troubleshooting Steps

### 1. **Check Running Containers**

The first step in troubleshooting is to check the status of the running Docker containers. You can do this by using the following command:

```bash
docker ps
```

This command will list all the running containers, showing their container IDs, names, and other important information.

### 2. **View Logs**

Once you have the container ID of the Knotie-AI service, you can view the logs to diagnose any issues. Use the following command to view the logs:

```bash
docker logs -f <container_id>
```

Replace `<container_id>` with the actual container ID from the previous step.

The `-f` flag allows you to follow the log output in real-time, which can be helpful for monitoring the application as it runs.

---

## ⚠️ Common Issues and Fixes

While the above steps cover the basic troubleshooting approach, more detailed information and common fixes will be provided in future updates.

Stay tuned!

---

## ❓ Need More Help?

If you're unable to resolve the issue using the above steps, consider reaching out to the community:

- [Join our Discord Community](https://discord.com/invite/link)
- [Watch the Video Tutorials](https://youtube.com/link-to-videos)

We’re here to help!