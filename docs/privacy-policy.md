---
layout: default
title: Privacy Policy — LinkedIn MCP Server
---

# Privacy Policy

**LinkedIn MCP Server**
Last updated: 21 June 2026

## Overview

LinkedIn MCP Server is an open-source tool that connects AI assistants (such as Claude) to your LinkedIn account via LinkedIn's official API. This privacy policy explains what data the application accesses, how it is handled, and your rights.

## What Data Is Collected

When you authenticate with LinkedIn through this application, the following data is accessed:

- **Profile information**: Your name, profile picture URL, locale, and email address (via LinkedIn's OpenID Connect userinfo endpoint)
- **Authentication tokens**: An OAuth 2.0 access token issued by LinkedIn, stored locally on your device

When you use the posting features, the application sends content you have explicitly approved to LinkedIn's API on your behalf.

## How Data Is Used

- **Profile data** is retrieved on demand when you request it and is displayed to you directly. It is not cached, stored, or transmitted to any third party.
- **Authentication tokens** are stored locally on your device (by default at `~/.linkedin-mcp/tokens.json`) solely to maintain your authenticated session. Tokens are never transmitted to any server other than LinkedIn's API.
- **Post content** is sent only to LinkedIn's official API (`api.linkedin.com`) and only after you have explicitly reviewed and approved each post.

## Data Sharing

This application does **not** share, sell, rent, or disclose any of your data to third parties. All communication is directly between your device and LinkedIn's official API servers.

## Data Storage

- All data is stored **locally on your device only**.
- No data is sent to any server operated by the developers of this application.
- No analytics, telemetry, or tracking of any kind is performed.

## Data Retention

- **Authentication tokens** are stored until they expire (60 days) or until you explicitly log out using the `linkedin_logout` tool.
- **Profile data** is not stored — it is fetched fresh each time you request it.
- **Post content** is not stored by this application after being sent to LinkedIn.

## Your Rights

You can exercise the following rights at any time:

- **Withdraw consent**: Use the `linkedin_logout` tool to revoke your session, or revoke the application's access from your [LinkedIn Settings](https://www.linkedin.com/psettings/permitted-services).
- **Request deletion**: Use `linkedin_logout` to delete all locally stored tokens. Since no other data is stored, this constitutes full deletion of all data held by the application.
- **Access your data**: Use the `linkedin_profile` tool to see what profile data LinkedIn makes available to the application.

## Security

- Authentication is handled entirely by LinkedIn's OAuth 2.0 flow — your LinkedIn password is never seen or handled by this application.
- Tokens are stored as plain JSON on your local filesystem. You are responsible for securing access to your device.

## Children's Privacy

This application is not intended for use by individuals under the age of 16.

## Changes to This Policy

Changes to this privacy policy will be published to this page with an updated date. For significant changes, a notice will be included in the project's release notes.

## Contact

If you have questions about this privacy policy, please open an issue on the [GitHub repository](https://github.com/anubisalpha/linkedin-mcp/issues).
