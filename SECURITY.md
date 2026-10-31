# Security policy for RasterReady

## Supported versions

RasterReady 0.1.0 is the current stable release. Fixes target the latest stable version, with no promised backports. Identify the version or source commit in a report; development builds are not supported stable releases.

## Private reporting

Use [GitHub private vulnerability reporting](https://github.com/rdcstout/RasterReady/security/advisories/new). This repository has that feature enabled; the policy file itself does not enable it. Do not put vulnerability details, exploit instructions, private images, credentials or user data in a public issue, PR or attachment. Ordinary bugs and feature requests can use public issues.

Include the commit/version, operating system, affected component, minimal sanitized reproduction, required access and potential impact. A credible concern does not require a complete exploit. Relevant concerns include failure to remove embedded personal metadata, reading unintended local files, modifying originals, unsafe handling of untrusted images, and update destination manipulation. Visible information in an image is not embedded metadata.

Only assess systems and disposable files you own or are authorized to test. Avoid disruption and other people's data. If uncertain whether an issue is security-sensitive, keep the details private until a reporting route is available.

## Handling and disclosure

Reports are assessed on a best-effort basis. We may request clarification and coordinate verification, fixes and disclosure. Keep details private while a response and disclosure timing are discussed through the private channel. There are no guaranteed acknowledgement/fix dates, guaranteed fixes or standing paid bounty. Agree reporter credit before publication. This policy does not warrant that the app is free of vulnerabilities.
