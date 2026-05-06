job "qwen-tts-server" {
  datacenters = ["dc1"]
  type        = "service"

  update {
    max_parallel     = 1
    health_check     = "task_states"
    min_healthy_time = "30s"
    healthy_deadline = "5m"
    auto_revert      = true
    stagger          = "30s"
  }

  reschedule {
    attempts       = 6
    interval       = "30m"
    delay          = "15s"
    delay_function = "exponential"
    max_delay      = "120s"
    unlimited      = false
  }

  group "backend" {
    count = 1

    restart {
      attempts = 3
      interval = "5m"
      delay    = "15s"
      mode     = "fail"
    }

    migrate {
      max_parallel     = 1
      health_check     = "task_states"
      min_healthy_time = "30s"
      healthy_deadline = "5m"
    }

    task "qwen-tts" {
      driver = "raw_exec"

      config {
        command = "/opt/qwen-tts-server/current/venv/bin/python"
        args    = ["/opt/qwen-tts-server/current/main.py"]
      }

      env {
        HF_HOME                   = "/opt/qwen-tts-server/cache/hf"
        HF_HUB_ENABLE_HF_TRANSFER = "1"
        PYTHONPATH                = "/opt/qwen-tts-server/current"
        QWEN_TTS_HOST             = "0.0.0.0"
        QWEN_TTS_PORT             = "8000"
      }

      service {
        name = "qwen-tts-server"
        tags = ["tts", "ai", "fastapi", "python"]
        meta {
          description      = "Qwen3-TTS REST API Server - Generacion de voz con modelos Qwen3"
          version          = "3.1.0"
          stack            = "python/fastapi"
          model_hot        = "CustomVoice (always loaded)"
          model_lazy       = "VoiceDesign + Base/Clone (on demand, VRAM pool)"
          manage           = "nomad job restart/stop qwen-tts-server"
        }
        port = "http"

        check {
          type     = "http"
          name     = "Health"
          path     = "/health"
          interval = "15s"
          timeout  = "5s"
          address_mode = "host"
        }

        check_restart {
          limit           = 3
          grace           = "90s"
          ignore_warnings = false
        }
      }
    }

    network {
      port "http" {
        static = 8000
      }
    }
  }
}
