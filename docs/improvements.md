---
title: Further Improvements
description: Suggestions for further improvements and future work on Knotie-AI.
tags: Improvements, Future Work, Knotie-AI
---

# 🚀 Further Improvement Suggestions

Here are some suggestions for further improvements and future work on Knotie-AI:

1. **Update Prompts**: Please update prompts as per your business use cases. The provided prompts in `prompts.py` are very generalized and inspired by the 'SalesGPT' Open Source Project.

2. **Adjust Sales Stages**: Adjust Sales Stages based on your requirement. The current Sales Stages provided in `stages.py` are very generalized and inspired by the 'SalesGPT' Open Source Project.

3. **Test AI Outputs**: If you want to test AI outputs before integrating with Twilio and ElevenLabs API first, there is a section commented out in `ai_helpers.py`. You can modify and use that section to test. Only make changes to the file if you have knowledge in Python; otherwise, it may break the application.

4. **Evaluation Script**: An `evaluation.py` will be created to allow you to evaluate and test AI Agents before you run it for your use case (This is currently Work In Progress).

5. **State Management**: The current code relies on Redis for in-memory state management. File-based and cloud database support will be included for users who can't run Docker in their local (Redis in their local) due to lower system specification. (Work In Progress).

6. **Cloud Deployment Guide**: A guide on how to deploy this on the cloud will be included (Work In Progress).

7. **Wordpress Plugin**: The Wordpress plugin will be updated to support tool calling, email address collection from customers, etc. (Work In Progress).

8. **Suggestions and Feedback**: If you have any other suggestions, please join the [Discord](https://discord.com/invite/7UKpgUbEXf) and raise your suggestion or feedback using the **gumroad-product-support** channel.