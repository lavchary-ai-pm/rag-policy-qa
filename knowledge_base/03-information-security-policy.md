# NorthStar Labs - Information Security Policy

**Document ID:** IT-SEC-001
**Effective Date:** January 1, 2025
**Last Updated:** March 1, 2025
**Approved By:** Marcus Webb, Chief Information Security Officer
**Compliance:** SOC 2 Type II, ISO 27001, HIPAA (for healthcare clients)

---

## 1. Purpose and Scope

This policy establishes information security requirements for all NorthStar Labs employees, contractors, and third-party vendors with access to NorthStar systems or data. Violations of this policy may result in disciplinary action up to and including termination, as outlined in the Code of Conduct (HR-COC-001).

---

## 2. Data Classification

### 2.1 Classification Levels

**Restricted (Level 4)**
- Customer PII (names, SSNs, financial data)
- Customer production data
- Authentication credentials and API keys
- Encryption keys and certificates
- Employee health information (HIPAA-protected)
- Board materials and M&A information

**Confidential (Level 3)**
- Source code and proprietary algorithms
- Internal financial reports and forecasts
- Employee compensation data
- Customer contracts and pricing
- Product roadmaps and unreleased feature plans
- Security audit reports and vulnerability assessments

**Internal (Level 2)**
- Internal communications (Slack, email)
- Meeting recordings and notes
- Internal documentation (Confluence)
- Employee directory information (name, title, department, work email)
- Non-sensitive operational data

**Public (Level 1)**
- Published marketing materials
- Public-facing documentation
- Open-source code contributions
- Press releases and public financial filings

### 2.2 Data Handling Requirements

| Classification | Storage | Sharing | Disposal |
|---------------|---------|---------|----------|
| Restricted | Encrypted at rest and in transit. Approved systems only (see Section 4). Access logged. | Need-to-know basis. No email. Encrypted transfer only. Approval from data owner required. | Secure deletion with certificate. 7-year retention for financial data. |
| Confidential | Encrypted at rest. Company-managed systems only. | Within company only. External sharing requires NDA and CISO approval. | Secure deletion. Retain per department retention schedule. |
| Internal | Company-managed systems. | Internal only. No external sharing without manager approval. | Standard deletion. |
| Public | No restrictions. | No restrictions. | No special requirements. |

---

## 3. Access Control

### 3.1 Authentication Requirements
- All NorthStar systems require Single Sign-On (SSO) through Okta
- Multi-Factor Authentication (MFA) is mandatory for all employees. Acceptable MFA methods: hardware security key (preferred), authenticator app (Google Authenticator, Authy). SMS-based MFA is not permitted.
- Passwords must be minimum 14 characters with at least one uppercase, one lowercase, one number, and one special character
- Passwords must not be reused across any systems (personal or work)
- Password manager (1Password) is provided to all employees and its use is mandatory

### 3.2 Access Provisioning
- Access to systems is granted based on the principle of least privilege
- Access requests must be submitted through the IT Service Desk (ServiceNow)
- Production environment access requires approval from the employee's manager AND the system owner
- Access to Restricted (Level 4) data requires additional approval from the CISO
- All access is reviewed quarterly. Managers must certify their team's access within 5 business days of review notification

### 3.3 Offboarding
- IT must be notified at least 2 business days before an employee's last day
- All access is revoked within 4 hours of the employee's termination effective time
- Company equipment must be returned within 5 business days of the last day
- For remote employees, a prepaid shipping label is provided by IT

---

## 4. Approved Systems and Tools

### 4.1 Approved for All Data Classifications
- AWS (us-east-1 and us-west-2 regions only for Restricted data)
- Google Workspace (email, Drive, Docs)
- Salesforce (CRM data)
- Snowflake (analytics)
- GitHub Enterprise (source code)
- Jira/Confluence (project management)
- Slack Enterprise Grid (with DLP enabled)
- Workday (HR data)
- 1Password (credential management)

### 4.2 Prohibited Tools
The following categories of tools may NOT be used for any NorthStar business data:
- Personal email accounts (Gmail, Yahoo, Outlook.com)
- Personal cloud storage (personal Google Drive, Dropbox, iCloud)
- Consumer messaging apps (WhatsApp, iMessage, Telegram, Signal) for business communication
- Unapproved AI tools (see Section 7 for AI-specific policy)
- USB flash drives or external hard drives (except encrypted drives issued by IT)
- Public file-sharing services (WeTransfer, Mega, etc.)

### 4.3 New Tool Requests
Requests for new tools or software must be submitted through the IT Service Desk with a completed Vendor Security Assessment form. Tools processing Restricted or Confidential data require a full security review (typically 2-4 weeks). Tools processing only Internal data may be fast-tracked (typically 3-5 business days).

---

## 5. Device Security

### 5.1 Company-Issued Devices
- All company laptops run endpoint protection (CrowdStrike Falcon)
- Full disk encryption (FileVault for Mac, BitLocker for Windows) is enforced
- Automatic OS updates are enforced with a maximum 7-day deferral
- Screen lock is enforced after 5 minutes of inactivity
- Remote wipe capability is enabled on all devices

### 5.2 BYOD (Bring Your Own Device)
Personal devices may be used to access company email and Slack only if:
- The device has a screen lock with biometric or PIN
- The device OS is within 2 major versions of current (e.g., iOS 17+ for iPhones as of 2025)
- NorthStar's Mobile Device Management (MDM) profile is installed (Jamf)
- The employee acknowledges that NorthStar may remotely wipe company data (not personal data) from the device

Personal devices may NOT be used to access:
- Production environments
- Customer data
- Source code repositories
- Financial systems

### 5.3 Lost or Stolen Devices
Report immediately to IT Security (security@northstarlabs.com) and your manager. Do NOT wait until the next business day. IT will initiate remote wipe within 1 hour of notification. A replacement device will be shipped within 2 business days.

---

## 6. Network Security

### 6.1 VPN Requirements
VPN (Zscaler) is required when:
- Accessing internal systems from outside a NorthStar office
- Connecting to any network other than a NorthStar office network
- Accessing Restricted or Confidential data from any location

VPN is NOT required for:
- Accessing email and Slack from a personal mobile device with MDM
- Accessing public-facing NorthStar websites

### 6.2 Public Wi-Fi
Employees should avoid public Wi-Fi networks when possible. When public Wi-Fi is necessary, VPN must be connected BEFORE accessing any NorthStar systems. Coffee shop and hotel Wi-Fi are considered public networks.

### 6.3 Home Network
Remote employees should ensure their home Wi-Fi uses WPA3 or WPA2 encryption. Default router passwords must be changed. Router firmware should be updated regularly.

---

## 7. Artificial Intelligence Usage Policy

### 7.1 Approved AI Tools
The following AI tools are approved for use with NorthStar data:
- **GitHub Copilot Business** - approved for code completion with company source code
- **Claude (Anthropic) via API** - approved for internal use with Internal (Level 2) data only
- **ChatGPT Enterprise (OpenAI)** - approved for internal use with Internal (Level 2) data only
- **Grammarly Business** - approved for writing assistance with Internal data

### 7.2 AI Usage Restrictions
- **Restricted (Level 4) data must NEVER be input into any AI tool**, including approved tools
- **Confidential (Level 3) data must NEVER be input into any AI tool** unless the tool has been specifically approved by the CISO for that data type (currently no tools are approved for Confidential data in AI contexts)
- Customer data, customer names, or any PII must not be used in AI prompts
- AI-generated code must be reviewed by a human before being committed to any repository
- AI-generated content for external use (customer communications, marketing) must be reviewed and approved by the content owner

### 7.3 Prohibited AI Uses
- Using free-tier or personal AI accounts (ChatGPT free, Claude free, Gemini) for any work-related purpose
- Training or fine-tuning AI models on NorthStar data without CISO approval
- Using AI to generate security assessments, penetration test reports, or compliance documentation without human expert validation
- Uploading source code to AI tools not listed in Section 7.1
- Using AI-generated images for official NorthStar marketing without legal review

### 7.4 AI Incident Reporting
If you accidentally input Restricted or Confidential data into an AI tool:
1. Stop immediately and do not submit additional prompts
2. Report to IT Security within 1 hour (security@northstarlabs.com)
3. Document what data was shared and which tool was used
4. IT Security will assess the risk and take appropriate action
5. This is not punitive if reported promptly. Failure to report is a policy violation.

---

## 8. Incident Response

### 8.1 Reporting Security Incidents
All employees must report suspected security incidents immediately to:
- Email: security@northstarlabs.com
- Slack: #security-incidents (24/7 monitored)
- Phone (after hours): Security on-call number in 1Password vault "Emergency Contacts"

Security incidents include but are not limited to:
- Phishing emails (forward to phishing@northstarlabs.com, do NOT click links)
- Unauthorized access to systems or data
- Lost or stolen devices
- Suspicious account activity
- Data sent to wrong recipient
- Physical security breaches (tailgating, unescorted visitors)

### 8.2 Incident Severity Classification

| Severity | Definition | Response Time |
|----------|-----------|---------------|
| Critical (P1) | Active data breach, ransomware, or system compromise affecting customer data | 15 minutes |
| High (P2) | Potential data exposure, compromised employee account, or significant vulnerability | 1 hour |
| Medium (P3) | Policy violation without data exposure, phishing attempt (not clicked), suspicious activity | 4 hours |
| Low (P4) | Minor policy questions, false positive alerts, general security inquiries | 1 business day |

---

## 9. Training Requirements

### 9.1 Security Awareness Training
- All employees must complete annual security awareness training through KnowBe4
- New employees must complete training within 14 days of their start date
- Training completion is tracked and reported to managers. Non-completion after 30 days will result in restricted system access until training is completed.

### 9.2 Phishing Simulations
IT Security conducts monthly phishing simulations. Employees who click on simulated phishing links will receive additional targeted training. Three failures within a 12-month period results in a meeting with the employee's manager and IT Security to develop a personalized security improvement plan.

### 9.3 Role-Specific Training
- Engineers with production access: Additional secure coding training (annually)
- Managers: Access review and data handling training (annually)
- Employees handling Restricted data: Data handling certification (annually, plus refresher when classification standards change)

---

## 10. Compliance and Auditing

### 10.1 Audits
IT Security conducts:
- Quarterly access reviews
- Annual penetration testing (third-party)
- Continuous vulnerability scanning
- Monthly compliance checks against SOC 2 controls

### 10.2 Record Retention
Security logs are retained for minimum 1 year. Access logs for Restricted data are retained for 7 years. Incident reports are retained for 5 years.

### 10.3 Policy Exceptions
Exceptions to this policy require written approval from the CISO and the requesting employee's VP. Exceptions are reviewed quarterly and must be renewed annually. All exceptions are documented in the Security Exception Register.
