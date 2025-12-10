# Security Policy

## Project Overview

This repository contains the source code for the **Auto Filter Bot**, a Telegram bot designed for educational purposes to demonstrate automated media filtering and group management using Pyrogram and MongoDB. The bot provides features like auto-filtering, group settings customization, and link shortening. We are committed to maintaining a secure codebase and appreciate your help in identifying vulnerabilities.

## Supported Versions

The following versions of the Auto Filter Bot are currently supported for security updates:

| Version | Supported          |
|---------|--------------------|
| 4.3     | :white_check_mark: |
| 4.2     | :x:                |

We strongly recommend using the latest version (**4.2**) to benefit from security fixes and improvements. Older versions, including **2.2**, are not supported and may contain unpatched vulnerabilities.

## Reporting a Vulnerability

If you discover a security vulnerability in the Auto Filter Bot, please report it to us privately to protect our users and learners. We encourage responsible disclosure and appreciate your efforts to keep our project safe.

To report a vulnerability, please contact us via Telegram:

- **Telegram**: Send a private message to [SilentXBotz_Support](https://t.me/SilentXBotz_support)

When reporting, include the following details to help us address the issue quickly:

- A description of the vulnerability (e.g., how it can be exploited and its impact).
- Steps to reproduce the issue or a proof-of-concept (if possible).
- Affected version (e.g., 4.2 or 2.2) and components (e.g., Pyrogram, MongoDB, group settings).
- Your Telegram handle or contact information (optional, for follow-up).

We will acknowledge your report within **48 hours** and work with you to validate and resolve the issue.

## Disclosure Process

1. **Acknowledgment**: We will confirm receipt of your report within 48 hours and provide an estimated timeline for investigation.
2. **Investigation**: Our team will verify the vulnerability, assess its impact, and identify necessary fixes.
3. **Resolution**: We will develop and test patches, coordinating with you if needed.
4. **Public Disclosure**: Once resolved, we will publish a security advisory or update this repository, crediting you (if you wish to be acknowledged).
5. **Timeline**: We aim to resolve critical issues within **30 days** and less severe issues within **90 days**, depending on complexity.

## Security Best Practices

To securely use or contribute to the Auto Filter Bot, we recommend:

- **Secure Credentials**:
  - Never expose your Telegram bot token, MongoDB URI, or API keys (e.g., `SHORTENER_API`) in public repositories or logs.
- **Update Dependencies**:
  - Regularly update Pyrogram, Motor, and other Python libraries to patch known vulnerabilities.
  - Run `pip install --upgrade pyrogram motor` to stay current.
- **Contributions**:
  - Follow secure coding practices when modifying the bot (e.g., validate inputs, sanitize URLs).
  - Test changes in a private group before deploying to public groups.

## Scope

This security policy applies to the main branch and official releases of the Auto Filter Bot repository (versions 4.2 and above). Issues in third-party dependencies (e.g., Pyrogram, Motor) or forks are outside our scope, but we encourage reporting them to their respective maintainers.

## Acknowledgments

We deeply value the contributions of security researchers and learners who help secure our educational project. If you report a valid vulnerability, we will acknowledge you in our release notes or security advisories (unless you prefer anonymity).

Thank you for supporting the Auto Filter Bot and keeping our community safe!

---

*Last updated: June 19, 2025*
