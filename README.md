# Vietnamese Speech-to-Text

Ứng dụng desktop nhận dạng tiếng Việt hoàn toàn local trên Windows 10/11. Silero VAD tách từng phát ngôn; Zipformer offline Transducer nhận dạng sau khi người nói kết thúc câu. Đây là nhận dạng theo từng phát ngôn, không phải transcript từng từ. Âm thanh chỉ ở trong RAM và không được lưu mặc định.

## Cài đặt

Cần Windows 10/11 64-bit, Python **3.11 64-bit**, microphone và CPU. Internet chỉ cần cho lần cài gói và tải model đầu tiên. Gói PySide6-Essentials cung cấp các module PySide6.QtWidgets, QtCore và QtGui mà ứng dụng sử dụng. SoXR xử lý resampling khi microphone không hỗ trợ 16 kHz.

Trong dự án này đã có môi trường .venv311 dùng Python 3.11. Trong PowerShell, tại thư mục dự án:

    .\.venv311\Scripts\Activate.ps1
    python -m pip install --upgrade pip
    python -m pip install -r requirements.txt
    python scripts/download_models.py
    python scripts/check_microphone.py
    python scripts/diagnose.py --wav models/zipformer-vi-30m-int8/test_wavs/0.wav --vad-wav
    python main.py

Nếu sao chép mã sang máy khác hoặc cần tạo lại môi trường, chạy py -3.11 -m venv .venv311 khi Python launcher nhận diện được bản 3.11. Nếu launcher không tìm thấy Python, dùng đường dẫn trực tiếp đến python.exe của bản 3.11; trên máy đang phát triển là C:\Users\BNK-HuyBG2\AppData\Local\Programs\Python\Python311\python.exe. Nếu PowerShell chặn activation, dùng trực tiếp .\.venv311\Scripts\python.exe thay cho python. Không cần đổi execution policy. Script tải model kiểm tra file đã tồn tại và cho phép chạy lại sau lỗi.

Để thử microphone và VAD trước khi mở giao diện:

    python scripts/diagnose.py --mic 10

Script in thời gian xử lý và số ký tự nhận dạng. Kiểm thử WAV cần file mono PCM 16-bit 16 kHz.

## PyCharm

1. Mở thư mục dự án qua File → Open.
2. Vào Settings → Project → Python Interpreter → Add Interpreter → Select Existing, chọn .venv311\Scripts\python.exe. Nếu tự tạo virtualenv mới, chọn base interpreter Python 3.11 64-bit. .venv hiện tại dùng Python 3.14 và không phù hợp.
3. Trong Terminal của PyCharm, cài dependencies, tải model và kiểm tra microphone theo các lệnh trên.
4. Mở main.py, chọn interpreter 3.11 rồi nhấn Run.

## Sử dụng

Chọn microphone, nhấn Bắt đầu, nói và ngừng một lúc. Văn bản xuất hiện sau khi VAD phát hiện kết thúc phát ngôn. Có thể nói tiếp nhiều câu. Tạm dừng/Tiếp tục điều khiển thu âm; Dừng đóng luồng microphone. Copy Text, Clear Text và Export TXT thao tác với văn bản. Export tạo file UTF-8 tại vị trí bạn chọn.

Model được tải một lần lúc khởi động. Đặt biến môi trường STT_CPU_THREADS trước khi chạy để chỉnh số luồng suy luận, ví dụ: $env:STT_CPU_THREADS=4. Mặc định là 2.

## Model và API

Script tải [Zipformer Vietnamese 30M INT8 (2026-02-09)](https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-zipformer-vi-30M-int8-2026-02-09.tar.bz2) và [Silero VAD](https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/silero_vad.onnx). Tên file Zipformer được xác minh theo [tài liệu chính thức](https://github.com/k2-fsa/sherpa/blob/master/docs/source/onnx/pretrained_models/offline-transducer/zipformer-transducer-models.rst): encoder.int8.onnx, decoder.onnx, joiner.int8.onnx và tokens.txt. API Python theo [ví dụ VAD + offline ASR](https://github.com/k2-fsa/sherpa-onnx/blob/master/python-api-examples/vad-with-non-streaming-asr.py) và [OfflineRecognizer](https://github.com/k2-fsa/sherpa-onnx/blob/master/sherpa-onnx/python/sherpa_onnx/offline_recognizer.py).

Model nằm trong models/ và được .gitignore loại khỏi Git. Nếu tải thủ công, đặt file Zipformer trong models/zipformer-vi-30m-int8/ và VAD tại models/silero_vad.onnx.

## Xử lý lỗi

- Thiếu model: chạy lại python scripts/download_models.py và kiểm tra Internet, dung lượng đĩa.
- Không có microphone: kiểm tra kết nối và quyền truy cập Windows trong Settings → Privacy & security → Microphone, rồi nhấn Làm mới.
- Microphone bị chiếm dụng hoặc mất kết nối: đóng ứng dụng khác đang dùng mic, chọn lại thiết bị và nhấn Bắt đầu.
- Sample rate không hỗ trợ: ứng dụng thử 16 kHz trước, rồi sample rate mặc định và resample về 16 kHz. Chạy check_microphone.py để xác định thiết bị dùng được.
- Hàng đợi đầy: giảm tải CPU hoặc thử tăng STT_CPU_THREADS. Ứng dụng báo lỗi thay vì bỏ âm thanh âm thầm.
- Không có văn bản: nói rõ và chờ khoảng nửa giây sau câu; VAD có thể loại tiếng ồn và đoạn quá ngắn.
- Lỗi ONNX/import: kiểm tra interpreter Python 3.11 64-bit, cài lại dependencies và tải lại model nếu file hỏng.

## Cấu trúc

    main.py                       điểm khởi động
    config.py                     cấu hình và đường dẫn model
    app/audio_capture.py          thiết bị và resampling
    app/vad_processor.py          cắt phát ngôn
    app/speech_recognizer.py      nhận dạng
    app/model_manager.py          kiểm tra và khởi tạo model
    app/workers.py                capture, VAD và ASR workers
    app/ui.py                     giao diện PySide6
    scripts/download_models.py    tải và xác minh model
    scripts/check_microphone.py   kiểm tra thiết bị
    scripts/diagnose.py           kiểm thử độc lập

## Backend FastAPI

Desktop tiếp tục chạy bằng main.py. Backend dùng cùng model Zipformer offline và Silero VAD, trả kết quả cuối mỗi phát ngôn. Model ASR được tải một lần mỗi tiến trình, các phiên có VAD riêng và ASR được khóa để tránh truy cập đồng thời. Không có transcript partial.

Trong PowerShell, sau khi chọn Python 3.11:

    .\.venv311\Scripts\python.exe -m pip install -r requirements.txt
    .\.venv311\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1 --ws-max-size 32768 --ws-max-queue 8 --ws-ping-interval 20 --ws-ping-timeout 20

Mở http://127.0.0.1:8000 để dùng demo; tài liệu API tại /docs. AudioWorklet gửi PCM 16-bit mono theo sample rate thực của trình duyệt; server chuyển về 16 kHz. Microphone trình duyệt yêu cầu localhost hoặc HTTPS. API không gửi audio đến dịch vụ cloud và không lưu audio hay transcript.

- GET /api/v1/health: trạng thái model.
- GET /api/v1/models/current: thông tin model và chế độ suy luận.
- POST /api/v1/transcriptions: multipart form với file WAV và language=vi; hỗ trợ PCM 16-bit mono/stereo 8–48 kHz, tối đa 20 MB và 120 giây. Nếu bật API key, gửi header X-API-Key.
- WebSocket /api/v1/stt/stream: gửi JSON start gồm type, sample_rate, channels=1, encoding=pcm_s16le, language=vi và api_key khi cần. Sau ready, gửi các frame binary tối đa 32768 byte. Server gửi transcript.final với sequence và processing_time_ms. Gửi type=stop để flush rồi nhận session.completed. Có thể gửi type=ping để nhận pong. Lỗi có type=error.

Ví dụ kiểm thử:

    .\.venv311\Scripts\python.exe -m pip install -r requirements-test.txt
    .\.venv311\Scripts\python.exe -m unittest discover -s tests -v
    .\.venv311\Scripts\python.exe scripts/check_api.py

Script cuối chạy model thật với WAV mẫu qua REST và WebSocket. Không dùng nhiều Uvicorn workers nếu muốn chỉ tải một bản model; giới hạn phiên áp dụng theo từng tiến trình. Max sessions mặc định 8, max session 600 giây, khoảng chờ message 30 giây. Nếu client gửi nhanh hơn server xử lý, hàng đợi WebSocket giới hạn bởi Uvicorn; client demo dừng nếu buffer gửi vượt 1 MB. Các giới hạn này không phải cam kết công suất hay độ trễ.

## Ubuntu VPS / Docker

Đặt model đã tải trong models/ rồi chạy:

    cp .env.example .env
    # Sửa STT_API_KEY và STT_ALLOWED_ORIGINS trong .env
    docker compose up -d --build
    docker compose logs -f

Compose mount model read-only, không tải lại model; image chạy CPU và một tiến trình Uvicorn, có healthcheck và giới hạn tài nguyên. Docker host cần quyền đọc model cho UID 10001. Đặt reverse proxy HTTPS/WSS phía trước; proxy cần hỗ trợ WebSocket upgrade, timeout đủ dài và giới hạn kích thước request. Không public trực tiếp backend production nếu chưa cấu hình proxy, HTTPS, API key, origin và giới hạn request. CORS/origin được thiết lập qua STT_ALLOWED_ORIGINS dạng danh sách phân cách bằng dấu phẩy. Production yêu cầu STT_API_KEY; browser demo yêu cầu người dùng nhập key, không nhúng key vào mã nguồn. WebSocket xác thực bằng api_key trong start hoặc header X-API-Key cho client không phải trình duyệt. Bảo vệ key trong HTTPS và tránh ghi message vào log proxy.

STT_CPU_THREADS, STT_MAX_SESSIONS, STT_MAX_SESSION_SECONDS, STT_VAD_THRESHOLD và STT_VAD_SILENCE được cấu hình qua biến môi trường. Chỉ WAV PCM 16-bit được hỗ trợ cho upload; lỗi file trả JSON success=false. Giới hạn upload trong ứng dụng được kiểm tra sau khi multipart được server phân tích: cấu hình giới hạn request tại reverse proxy để từ chối upload lớn trước khi vào ứng dụng. Chưa có rate limiting theo IP; dùng reverse proxy để áp dụng. Không benchmark khả năng chịu tải.

## CI/CD GitHub Actions và Dokploy

Workflow tại .github/workflows/workflow.yaml chạy CI cho pull request, push main và chạy thủ công. Chỉ push main hoặc workflow_dispatch từ main mới build/push image và deploy. Image được build cho linux/amd64 với tag latest và commit SHA. Dokploy Application phải trỏ tới Docker Hub image latest và deploy bằng API. Trigger API thành công chỉ xác nhận Dokploy nhận yêu cầu; workflow sau đó đợi public health endpoint tối đa 10 phút, nhưng health xanh không tự chứng minh ứng dụng đã pull chính xác SHA. Tắt Docker Hub webhook/auto-deploy và mọi auto-deploy Git integration khác để tránh deploy trùng.

Thêm các GitHub Actions repository secrets:

    DOCKERHUB_USERNAME
    DOCKERHUB_TOKEN
    DOCKERHUB_REGISTRY=docker.io
    DOKPLOY_URL=https://dokploy.hood.io.vn
    DOKPLOY_API_KEY
    DOKPLOY_APPLICATION_ID
    STT_HEALTH_URL=https://stt.hood.io.vn/api/v1/health   (tùy chọn)

DOCKERHUB_TOKEN nên là access token có quyền write cho repository vietnamese-stt; không dùng mật khẩu tài khoản. Tạo repository Docker Hub trước. DOKPLOY_APPLICATION_ID lấy từ Application đã tạo trong Dokploy. Tạo Dokploy Application kiểu Docker Image, image là <DOCKERHUB_USERNAME>/vietnamese-stt:latest, registry Docker Hub và pull/deploy khi API được gọi. Không cấu hình Docker Hub webhook để trigger thêm một lần deploy. Lưu API key, CORS origin, CPU threads và giới hạn phiên trong phần Environment của Application.

Trong Application, cấu hình persistent storage riêng của Dokploy, mount vào /app/models ở chế độ read-only. Tải model release chính thức, giải nén thư mục sherpa-onnx-zipformer-vi-30M-int8-2026-02-09 và đặt bốn file encoder.int8.onnx, decoder.onnx, joiner.int8.onnx, tokens.txt trong thư mục con /app/models/zipformer-vi-30m-int8; đặt silero_vad.onnx trực tiếp trong /app/models. Bảo đảm UID 10001 trong container có quyền đọc file. Volume của Compose local không được tự động chia sẻ với storage Application của Dokploy. Compose file phục vụ local/self-managed; pipeline production dùng Docker Image Application, không build source trên VPS.

Thiết lập Application domain stt.hood.io.vn, target container port 8000, HTTPS Let's Encrypt qua Traefik đang do Dokploy quản lý và bật WebSocket forwarding. Không publish port 8000 trực tiếp lên VPS; kiểm tra DNS A/AAAA trỏ tới VPS và domain không đụng router của ứng dụng khác. CORS STT_ALLOWED_ORIGINS chứa chính xác origin frontend, ví dụ https://hood.io.vn. Health endpoint vẫn công khai để kiểm tra. REST cần header X-API-Key; trình duyệt demo gửi key trong thông điệp WebSocket start. Dùng HTTPS/WSS.

Sau mỗi push main, xem Actions để biết CI, push image, Dokploy trigger và health check. Xem runtime logs trong Dokploy Application; Docker Hub chứa latest và SHA tương ứng trong log workflow. Rollback an toàn: đổi Dokploy image tag từ latest sang SHA đã biết ổn định rồi Redeploy; sau đó kiểm tra health. Có thể chuyển lại latest sau khi xử lý lỗi.

Các endpoint triển khai: https://stt.hood.io.vn/api/v1/health, /api/v1/models/current, POST /api/v1/transcriptions và wss://stt.hood.io.vn/api/v1/stt/stream. Workflow không truy vấn trạng thái deploy nội bộ của Dokploy; nó trigger REST API rồi xác minh public health. Điều đó không khẳng định tag SHA đang chạy. Kiểm tra deployment/log image digest trong Dokploy khi cần xác minh phiên bản chính xác.

Docker Compose không thể chạy container trong môi trường phát triển hiện tại nếu Docker daemon chưa bật. Compose YAML vẫn có thể kiểm tra độc lập bằng docker compose config. Dokploy API, DNS, certificate và VPS chưa được truy cập từ CI local nên cần cấu hình thủ công theo các bước trên.
