# Bukti Verifikasi

Semua angka di bawah ini diambil dari eksekusi nyata pada mesin uji (Linux, Docker
29.1.3, Compose 2.40.3, Jenkins LTS di container).

## 1. Unit test aplikasi

```text
$ python3 -m unittest discover -s tests -v
Ran 9 tests in 32.143s
OK
```

Sembilan test yang sama dijalankan ulang di dalam stage **Syntax Check** milik Jenkins
(container `python:3.11-slim`), hasil `Ran 9 tests in 33.396s — OK`.

## 2. Uji end-to-end lewat Nginx (17 pemeriksaan)

| # | Pemeriksaan | Hasil |
|---|---|---|
| 1 | `GET /api/health` | 200 `{"status": "ok"}` |
| 2 | `GET /api/logs` tanpa token | 401 |
| 3 | `POST /api/login` kredensial benar | 200 + token |
| 4 | `POST /api/login` password salah | 401 |
| 5 | `POST /api/logs` dengan token | 201 |
| 6 | `GET /api/logs` | 200, `total_hits` konsisten |
| 7 | `DELETE /api/logs?index=abc` | 400 |
| 8 | `DELETE /api/logs?index=99999` | 404 |
| 9 | `DELETE /api/logs?index=<valid>` | 200 |
| 10 | `total_hits` setelah hapus | berkurang 1 |
| 11 | `POST /api/visit` (publik) | 201 |
| 12 | `POST /api/visit` dengan page lain | 400 |
| 13 | `POST /api/logout` | 200 |
| 14 | token dipakai setelah logout | 401 |

Ringkasan: **17/17 lulus**.

## 3. Data immunity (Named Volume)

```text
volume         : visitor-log-data (driver local)
container      : 0d44ddfe4084  → dihapus dengan docker rm -f
container baru : db350288d47d  → dibuat ulang lewat docker compose up -d
sha256 sebelum : e4aec2101f98edaa838b074d539b99e73b058f2a32e188ef97a3ff16fe406a3c
sha256 sesudah : e4aec2101f98edaa838b074d539b99e73b058f2a32e188ef97a3ff16fe406a3c
jumlah record  : 1 → 1
health setelah : 200
```

Volume juga diperiksa setelah `docker compose down` (tanpa `-v`); sha256 tetap identik.

## 4. Pipeline Jenkins

| Build | Hasil | Catatan |
|---|---|---|
| #1 | FAILURE | health check memanggil `docker compose` tanpa `--env-file` |
| #2 | FAILURE | penyebab sama, build antre berikutnya |
| #3 | SUCCESS | perbaikan `--env-file` pada stage Health Check |
| #4 | SUCCESS | image di-tag commit SHA, bukan nomor build |
| #5 | SUCCESS | dipicu **webhook GitHub**, bukan tombol Build Now |

Build #4:

```text
Ran 9 tests in 33.417s
Built  visitor-log-backend:eb23b3afc563
Deployed visitor-log-backend:eb23b3afc563
Health check passed on attempt 1
Finished: SUCCESS
```

## 5. Webhook

- Endpoint Jenkins: `https://<subdomain>.trycloudflare.com/github-webhook/`
- Event: `push` saja, content type `application/json`
- Hook GitHub ID: `707893621`
- Delivery GitHub: `push` → **200 OK**
- Bukti build otomatis: `Started by GitHub push by argaulyaa`
  (`GitHubPushCause`, bukan `UserIdCause` — jadi bukan "Build Now")
- Build #5: **SUCCESS**, image `visitor-log-backend:ebb599191670` (sama dengan commit SHA),
  health check lulus attempt 1

## Catatan lingkungan

Jaringan host uji memutus koneksi keluar ke edge `ngrok` (`connection reset by peer`
setelah TLS pada semua edge: 52.220.126.110, 13.228.59.63, 18.141.102.200,
52.220.69.60). Karena itu tunnel publik memakai **Cloudflare Tunnel** yang setara
fungsinya; perintah `ngrok http 8080` tetap didokumentasikan di README dan dapat
dipakai pada jaringan lain.
