# certificates

Completion certificates with a PDF and a public verification link.

- One certificate per learner and course. The primary UUID is the public certificate ID. The verification code is used in the shareable link.
- Enrollment completion requires the existing lesson and quiz requirements plus a passing attempt on each published exam. The certificate grade combines the best completed quiz and exam attempts by points earned out of points possible. The grade is visible after exam scores are released.
- A cancellation or full refund revokes the learner's certificate. Verification shows the revocation and downloads are blocked. Qualifying again issues a fresh verification code.
- PDF rendering happens on the first authorized download or when a platform admin explicitly regenerates a certificate by ID. The file is reused when present and generated for the current verification URL and released grade.
- The QR code opens the public HTML page at `BACKEND_URL/certificates/verify/<code>/`. Use the address that the recipient can reach. A non-local origin is required with `DEBUG=False`.
- PDFs bundle Noto Sans, Noto Sans Bengali, and Noto Sans Devanagari under the SIL Open Font License. Complex scripts are shaped with HarfBuzz. Long names and course titles wrap within the page. [Noto font source](https://github.com/notofonts/noto-fonts/tree/main/hinted/ttf)

See the [API routes](../docs/API_ROUTES.md#apicertificates).
