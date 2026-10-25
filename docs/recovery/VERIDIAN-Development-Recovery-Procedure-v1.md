# VERIDIAN Development Backup and Recovery Procedure

Date established: October 21, 2026
Status: Initial recovery test completed; comprehensive acceptance testing pending.

## Backup locations
Primary: C:\Users\whody\VERIDIAN-Recovery
Secondary: E:\VERIDIAN-Recovery
Tertiary: G:\VERIDIAN-Recovery

**Recovery location note:** The paths above record the locations used when this procedure was established. On another computer, drive letters and user folders may differ. Confirm the correct backup location and available storage before restoring files. Always restore into a separate folder. Never overwrite the active VERIDIAN application or database.

Encrypted archive: VERIDIAN-recovery-secure-20261021.7z.gpg
Encryption: GnuPG symmetric AES-256.
The recovery passphrase must be stored securely and separately.

## Verified recovery contents
- 242 application source, configuration, documentation, and development-log files.
- SQLite database backup created using the SQLite backup API.
- Database integrity check passed.
- 61 database tables verified.
- Django core migrations applied through 0057.
- Encrypted archive decrypted and tested successfully.

## Restoration procedure
1. Copy the encrypted archive from a verified recovery drive.
2. Decrypt with GnuPG using the securely stored passphrase.
3. Extract the resulting 7z archive into an isolated restoration directory.
4. Restore the SQLite database into the restored backend directory.
5. Configure development settings and the restored SQLite database path.
6. Run Django system checks and verify migrations.
7. Install frontend dependencies using npm ci.
8. Run the frontend build.
9. Configure the restored Vite API proxy to use the restored backend.
10. Start Django and Vite on separate test ports.
11. Verify login, workspace navigation, and dashboard display.
12. Stop the temporary restored servers when testing is complete.

## October 21 recovery test
- Isolated restoration: C:\Users\whody\VERIDIAN-Restore-Test
- Restored Django backend: port 8001.
- Restored Vite frontend: port 5174.
- Django system checks: passed.
- Restored frontend build: passed.
- Browser login: successful.
- Customers & Projects workspace: displayed.
- Project Status Dashboard: displayed.
- Integration tests: 40 passed.

## Safeguards
- Never overwrite the active development database during a restore test.
- Keep restoration work isolated from the original application.
- Never share recovery passphrases or credentials in logs or chat.
- Keep at least one encrypted backup offline or offsite.
- Verify backup integrity and periodically repeat recovery testing.
- Do not perform production DocuSign signing during recovery tests.
- No Git commits, GitHub pushes, or production deployments without authorization.
- A full hands-on UI acceptance review and explicit approval are required before production release.

## Remaining work
- Document exact repeatable command sequences for disaster recovery.
- Test recovery from the encrypted archive itself into a clean directory.
- Perform comprehensive application workflow and permissions testing.
- Establish recurring backup frequency and retention requirements.
