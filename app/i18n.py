"""i18n - Detect OS language and provide translations."""

import locale
import os


def _detect_language() -> str:
    """Detect system language. Returns 'es', 'zh', 'ja', or 'en'."""
    try:
        loc, _ = locale.getlocale()
        if loc:
            if loc.startswith("es"):
                return "es"
            if loc.startswith("zh"):
                return "zh"
            if loc.startswith("ja") or loc.startswith("jp"):
                return "ja"
    except Exception:
        pass
    # Fallback to env var
    lang_env = os.getenv("LANG", os.getenv("LC_ALL", "")).lower()
    if "zh" in lang_env or "cn" in lang_env:
        return "zh"
    if "ja" in lang_env or "jp" in lang_env:
        return "ja"
    if "es" in lang_env:
        return "es"
    return "en"


_LANG = _detect_language()

_TRANSLATIONS = {
    "es": {
        "gpu_detected": "GPU detectada",
        "vram_total": "VRAM total",
        "vram_insufficient": "VRAM insuficiente para modelos 1.7B. Usando modelos 0.6B.",
        "force_17b": "Para forzar modelos 1.7B, setea QWEN_CUSTOM_VOICE_MODEL manualmente.",
        "no_cuda": "No se detecto GPU CUDA. Modo CPU activo.",
        "cpu_models": "Usando modelos 0.6B por defecto (mas rapidos en CPU).",
        "check_cuda": "Para forzar GPU, verifica que PyTorch CUDA este instalado.",
        "selected_models": "Modelos seleccionados",
        "customvoice": "CustomVoice",
        "voicedesign": "VoiceDesign",
        "voiceclone": "Base/Clone",
        "loading": "Cargando",
        "ready": "listo",
        "lazy_loading": "configurados para lazy loading",
        "auto_unload_active": "Auto-unload watcher activo (timeout",
        "shutdown": "Deteniendo servidor",
        "unloading": "Descargando",
        "free_vram": "para liberar VRAM",
        "unloaded": "descargado",
        "loaded": "cargado",
        "inactive_for": "inactivo por",
        "releasing": "Liberando",
        "calculating_prompt": "Calculando voice clone prompt",
        "prompt_calculated": "Prompt calculado en",
        "prompt_serialized": "Desserializando voice clone prompt",
        "customvoice_gen": "CustomVoice generado en",
        "voicedesign_gen": "VoiceDesign generado en",
        "voiceclone_gen": "VoiceClone generado en",
        "voiceclone_from_prompt": "VoiceClone (from prompt) generado en",
        "error_prompt": "Error creando voice clone prompt",
        "error_clone": "Error en voice clone",
        "error_generate": "Error generando desde prompt",
        "error_voices": "Error listando voces",
        "not_loaded": "no esta cargado aun",
    },
    "zh": {
        "gpu_detected": "已检测到 GPU",
        "vram_total": "总 VRAM",
        "vram_insufficient": "VRAM 不足以运行 1.7B 模型。正在使用 0.6B 模型。",
        "force_17b": "若要强制使用 1.7B 模型，请手动设置 QWEN_CUSTOM_VOICE_MODEL。",
        "no_cuda": "未检测到 CUDA GPU。CPU 模式已激活。",
        "cpu_models": "默认使用 0.6B 模型（在 CPU 上更快）。",
        "check_cuda": "若要强制使用 GPU，请检查是否已安装 PyTorch CUDA。",
        "selected_models": "已选择的模型",
        "customvoice": "CustomVoice",
        "voicedesign": "VoiceDesign",
        "voiceclone": "Base/Clone",
        "loading": "正在加载",
        "ready": "就绪",
        "lazy_loading": "已配置为懒加载",
        "auto_unload_active": "自动卸载监控已激活（超时",
        "shutdown": "正在关闭服务器",
        "unloading": "正在卸载",
        "free_vram": "以释放 VRAM",
        "unloaded": "已卸载",
        "loaded": "已加载",
        "inactive_for": "已闲置",
        "releasing": "正在释放",
        "calculating_prompt": "正在计算语音克隆提示",
        "prompt_calculated": "提示计算耗时",
        "prompt_serialized": "正在反序列化语音克隆提示",
        "customvoice_gen": "CustomVoice 生成耗时",
        "voicedesign_gen": "VoiceDesign 生成耗时",
        "voiceclone_gen": "VoiceClone 生成耗时",
        "voiceclone_from_prompt": "VoiceClone（从提示）生成耗时",
        "error_prompt": "创建语音克隆提示时出错",
        "error_clone": "语音克隆出错",
        "error_generate": "从提示生成时出错",
        "error_voices": "列出语音时出错",
        "not_loaded": "尚未加载",
    },
    "ja": {
        "gpu_detected": "GPU を検出しました",
        "vram_total": "VRAM 合計",
        "vram_insufficient": "1.7B モデルに対して VRAM が不足しています。0.6B モデルを使用します。",
        "force_17b": "1.7B モデルを強制するには、QWEN_CUSTOM_VOICE_MODEL を手動で設定してください。",
        "no_cuda": "CUDA GPU が検出されませんでした。CPU モードがアクティブです。",
        "cpu_models": "デフォルトで 0.6B モデルを使用（CPU 上で高速）。",
        "check_cuda": "GPU を強制するには、PyTorch CUDA がインストールされていることを確認してください。",
        "selected_models": "選択されたモデル",
        "customvoice": "CustomVoice",
        "voicedesign": "VoiceDesign",
        "voiceclone": "Base/Clone",
        "loading": "読み込み中",
        "ready": "準備完了",
        "lazy_loading": "レイジーローディング用に設定",
        "auto_unload_active": "自動アンロード監視アクティブ（タイムアウト",
        "shutdown": "サーバーをシャットダウン中",
        "unloading": "アンロード中",
        "free_vram": "VRAM を解放するため",
        "unloaded": "アンロード済み",
        "loaded": "ロード済み",
        "inactive_for": "非アクティブ時間",
        "releasing": "解放中",
        "calculating_prompt": "ボイスクローンプロンプトを計算中",
        "prompt_calculated": "プロンプト計算時間",
        "prompt_serialized": "ボイスクローンプロンプトを逆シリアル化中",
        "customvoice_gen": "CustomVoice 生成時間",
        "voicedesign_gen": "VoiceDesign 生成時間",
        "voiceclone_gen": "VoiceClone 生成時間",
        "voiceclone_from_prompt": "VoiceClone（プロンプトから）生成時間",
        "error_prompt": "ボイスクローンプロンプトの作成エラー",
        "error_clone": "ボイスクローンエラー",
        "error_generate": "プロンプトからの生成エラー",
        "error_voices": "ボイス一覧エラー",
        "not_loaded": "まだロードされていません",
    },
    "en": {
        "gpu_detected": "GPU detected",
        "vram_total": "Total VRAM",
        "vram_insufficient": "Insufficient VRAM for 1.7B models. Using 0.6B models.",
        "force_17b": "To force 1.7B models, set QWEN_CUSTOM_VOICE_MODEL manually.",
        "no_cuda": "No CUDA GPU detected. CPU mode active.",
        "cpu_models": "Using 0.6B models by default (faster on CPU).",
        "check_cuda": "To force GPU, verify PyTorch CUDA is installed.",
        "selected_models": "Selected models",
        "customvoice": "CustomVoice",
        "voicedesign": "VoiceDesign",
        "voiceclone": "Base/Clone",
        "loading": "Loading",
        "ready": "ready",
        "lazy_loading": "configured for lazy loading",
        "auto_unload_active": "Auto-unload watcher active (timeout",
        "shutdown": "Shutting down server",
        "unloading": "Unloading",
        "free_vram": "to free VRAM",
        "unloaded": "unloaded",
        "loaded": "loaded",
        "inactive_for": "inactive for",
        "releasing": "Releasing",
        "calculating_prompt": "Calculating voice clone prompt",
        "prompt_calculated": "Prompt calculated in",
        "prompt_serialized": "Deserializing voice clone prompt",
        "customvoice_gen": "CustomVoice generated in",
        "voicedesign_gen": "VoiceDesign generated in",
        "voiceclone_gen": "VoiceClone generated in",
        "voiceclone_from_prompt": "VoiceClone (from prompt) generated in",
        "error_prompt": "Error creating voice clone prompt",
        "error_clone": "Voice clone error",
        "error_generate": "Error generating from prompt",
        "error_voices": "Error listing voices",
        "not_loaded": "not loaded yet",
    },
}


def _t(key: str) -> str:
    """Translate a key based on detected OS language."""
    return _TRANSLATIONS.get(_LANG, _TRANSLATIONS["en"]).get(key, key)
