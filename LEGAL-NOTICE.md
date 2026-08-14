[中文](#中文)

<a id="english"></a>

# Legal and Release Notice

> This document is a project-maintainer notice, not legal advice.

## Project status

Document Parser for GoodNotes is an independent, community-developed open-source project. It is **not affiliated with, endorsed by, sponsored by, or officially connected to Goodnotes Limited**.

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

## Format Analysis and security

The project documents observations about file structures and implements parsers for those observations. It does **not** authorize users to circumvent security measures, authentication, access controls, DRM, licensing restrictions, or service restrictions.

Before distributing the project, users should review the terms applicable to their own use of Goodnotes and the laws of the relevant jurisdiction. Goodnotes' current Terms & Conditions contain restrictions concerning format analysis and circumvention, so this notice must not be read as a statement that every possible format analysis activity is permitted by contract or law.

## Accuracy

The documented field meanings are empirical observations, not official Goodnotes specifications. Unknown fields and version-specific behavior may change. No compatibility or accuracy guarantee is made.

## License

The original source code in this repository is licensed under the MIT License in `LICENSE`. That license applies to this project's original code; it does not grant rights to third-party documents, assets, trademarks, or other content processed by the software.

---

[English](#english)

<a id="中文"></a>

# 法律與發佈聲明 (Legal and Release Notice)

> 本文件為專案維護者聲明，非正式法律意見。

## 專案狀態 (Project status)

Document Parser for GoodNotes 是一套獨立且由社群開發的開源專案。本專案**與 Goodnotes Limited 沒有任何附屬、背書、贊助或官方合作關係**。

「Goodnotes」及其相關名稱、標誌與商標均為其各自所有者的財產。使用這些名稱僅為了識別本專案旨在支援與運作的軟體及文件格式。

## 適用範圍 (Scope)

本專案讀取使用者提供的 `.goodnotes` 檔案，並嘗試解析其公開可觀察的二進位結構。專案中**不包含** Goodnotes 應用程式原始碼、專利 SDK、身份驗證金鑰、DRM 金鑰或任何繞過安全或身份驗證控制的指示。

本專案旨在用於合法的用途，例如格式相容性、資料復原、個人文件檢視、格式分析研究、測試與開發（前提是使用者已獲授權存取該檔案）。

使用者有責任確保其使用本軟體及處理相關檔案時，符合適用法律、合約、授權條款及第三方權益。

## 切勿發佈私密或第三方內容 (Do not publish private or third-party content)

請勿提交或發佈：

- 包含個人或機密資訊的 `.goodnotes` 檔案；
- PDF、圖片、音訊、範本、貼圖、字型或任何未獲授權重新發佈的第三方內容；
- 憑證、Token、私鑰、雲端資料或帳號資訊；
- 未獲授權重新發佈的導出文件內容。

本專案儲庫的 `samples/` 目錄已刻意被忽略。本機研究檔案切勿視為可自動重新發佈的測試樣本。

## 格式分析與安全性 (Format Analysis and security)

本專案記錄有關檔案結構的觀察結果，並針對這些觀察實作解析器。專案**並未授權**使用者繞過安全措施、身份驗證、存取控制、DRM、授權限制或服務限制。

在散佈本專案之前，使用者應審閱適用於自身使用 Goodnotes 的條款及相關管轄區的法律。Goodnotes 現行的服務條款包含關於格式分析與繞過控制的限制，因此本聲明不得被視為允許合約或法律所禁止的所有格式分析活動。

## 精確性 (Accuracy)

本專案所記錄的欄位語意均為實證觀察結果，而非 Goodnotes 官方規格說明。未知欄位與特定版本的行為可能會有所變動。本專案不提供任何相容性或精確性保證。

## 授權條款 (License)

本專案庫中的原始專案源碼採用 `LICENSE` 中的 MIT 授權條款發佈。該授權條款僅適用於本專案本身的原始碼，並不授予本軟體所處理的第三方文件、資產、商標或其他內容的任何權利。
