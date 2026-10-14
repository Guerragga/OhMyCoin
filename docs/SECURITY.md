# Security

This is not a certified financial service. Static scans and tests reduce known risks but do not establish complete security.

## Implemented

- Werkzeug salted password hashing. Invalid/nonexistent users still perform a password-hash check.
- Password length limits and a documented password policy; passwords retain their exact whitespace.
- Session cookies: HttpOnly, SameSite=Lax by default and Secure required in production.
- Protected requests recheck active status, role and a password-version fingerprint. Password changes invalidate other authenticated sessions.
- CSRF on POST/PUT/PATCH/DELETE with a constant-time session-token comparison. Logout is POST-only.
- Fresh administrator checks in routes and mutating admin services.
- Owned financial object lookups and related-object validation by user ID.
- Parameterized SQL, including optional filters.
- Login limits per email/IP pair plus aggregate account and IP windows. Counters persist in MySQL and updates lock the counter row.
- CSP nonces, frame restrictions, MIME sniffing protection, referrer/permissions policies, and HTTPS-production HSTS.
- Production rejects debug/testing, missing/known-placeholder secrets, insecure cookies and empty DB passwords.

## Images and browser content

Image URLs allow HTTPS without credentials or nonstandard ports. Literal private/loopback/link-local IPs and common internal hostnames are rejected. The server **does not fetch or resolve these URLs**, so this feature is not a server-side HTTP proxy.

This validation does not prove that arbitrary public-looking hostnames resolve publicly forever. Browser-side fetching still creates privacy/tracking and DNS-rebinding considerations. A production image feature should use an allowlist or a separately secured image service rather than adding unrestricted server-side fetching.

Jinja escapes user content. CSRF HTML interpolates through Markup's escaping format operation. Deletion handlers live in external JavaScript rather than CSP-blocked inline attributes.

Bootstrap/Chart.js are CDN dependencies. The CSP permits the configured CDN; self-hosting assets/integrity pinning remains an improvement.

## Audit and sensitive data

Audit events contain action and internal object identifiers. Login handlers no longer put raw emails/IPs in audit messages. Audit failures log a fixed error message without exception/SQL contents.

The separate login_attempts table necessarily contains normalized email/IP values for throttling. It is operational security data, not an application log. Production needs a retention/deletion policy and restricted access. IDs may still be linkable personal data in a live system.

Do not enable verbose SQL logging or log request bodies, passwords, cookies, financial descriptions or tokens. A sanitized source tree says nothing about secrets previously committed: rotate any historically exposed credentials.

## Limits and deployment requirements

- Throttling is not a substitute for edge/WAF protections; concurrent in-flight attempts and registration abuse need broader controls.
- The default signup flow explicitly reports duplicate emails; use verified-email workflows and generic responses if account enumeration resistance is required.
- There is no MFA, password reset/email verification, dedicated session store or comprehensive intrusion monitoring.
- Proxy trust must only be enabled behind exactly the trusted proxy topology; direct untrusted access could spoof forwarded values.
- The local Compose file binds to loopback. Do not expose it unchanged as a public multi-user demo.
- Production needs HTTPS, persistent random secrets, a least-privilege database account, backups with tested restores, retention policies and monitoring.
- Review dependency advisories and rerun scans regularly.
- Public release must follow PUBLICATION.md. Never make the old repository public solely because its latest tree looks clean.

## Reporting

For a private deployment, report issues privately to its operator. Do not post credentials or real financial records in public issues.
