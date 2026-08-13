# Legal and Release Notice

> This document is a project-maintainer notice, not legal advice.

## Project status

GoodNotes Document Parser is an independent, community-developed open-source project. It is **not affiliated with, endorsed by, sponsored by, or officially connected to Goodnotes Limited**.

“Goodnotes” and related names, logos, and marks are the property of their respective owners. They are used only to identify the software and document format this project is intended to work with.

## Scope

This project reads user-supplied `.goodnotes` files and attempts to interpret their publicly observable binary structure. It does not contain Goodnotes application source code, proprietary SDKs, authentication credentials, DRM keys, or instructions for bypassing security or authentication controls.

The project is intended for legitimate uses such as interoperability, data recovery, personal-document inspection, format research, testing, and development with files the user is authorized to access.

Users are responsible for ensuring that their use of the software and the files they process complies with applicable law, contracts, licenses, and the rights of third parties.

## Do not publish private or third-party content

Do not commit or publish:

- `.goodnotes` files containing personal or confidential information;
- PDFs, images, audio, templates, stickers, fonts, or other third-party content unless redistribution is authorized;
- credentials, tokens, private keys, cloud data, or account information;
- extracted document contents that you do not have permission to redistribute.

The repository's `samples/` directory is intentionally ignored. Local research files must not be treated as automatically redistributable test fixtures.

## Reverse engineering and security

The project documents observations about file structures and implements parsers for those observations. It does **not** authorize users to circumvent security measures, authentication, access controls, DRM, licensing restrictions, or service restrictions.

Before distributing the project, users should review the terms applicable to their own use of Goodnotes and the laws of the relevant jurisdiction. Goodnotes' current Terms & Conditions contain restrictions concerning reverse engineering and circumvention, so this notice must not be read as a statement that every possible reverse-engineering activity is permitted by contract or law.

## Accuracy

The documented field meanings are empirical observations, not official Goodnotes specifications. Unknown fields and version-specific behavior may change. No compatibility or accuracy guarantee is made.

## License

The original source code in this repository is licensed under the MIT License in `LICENSE`. That license applies to this project's original code; it does not grant rights to third-party documents, assets, trademarks, or other content processed by the software.
