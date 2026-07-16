# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 1.0.x   | ✅        |
| < 1.0   | ❌        |

## Reporting a Vulnerability

Please **do not** open a public issue for security vulnerabilities.

Instead, report privately using GitHub's
[private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability)
("Report a vulnerability" under the repository's **Security** tab), or email the
maintainers if an address is listed on the project page.

When reporting, please include:

- A description of the vulnerability and its impact.
- Steps to reproduce or a proof of concept.
- Affected version(s) and environment.

We aim to acknowledge reports within 5 business days and to provide a fix or
mitigation timeline after triage.

## Scope

VidSmith downloads media through `yt-dlp` and processes it with `FFmpeg`.
Vulnerabilities in those upstream projects should be reported to them directly;
we will track and update our dependency pins as fixes are released.

## Safe Usage

- Only download content you are authorized to access.
- VidSmith writes files to the directory you choose — review output paths when
  scripting it in automated contexts.
