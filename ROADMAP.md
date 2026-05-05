# Roadmap / Mejoras por implementar

## Voice Clone — Calidad cross-lingual

### Contexto
Las voces clonadas suenan bien en el idioma nativo del hablante, pero la pronunciación en otros idiomas (ej: inglés para hablantes de español) está lejos de sonar nativa. Qwen3-TTS Base model usa un prompt compuesto por:
- `ref_spk_embedding` (x-vector ECAPA-TDNN): timbre
- `ref_code` (speech tokenizer): prosodia + fonética del audio de referencia
- `ref_text`: transcript alineado

### Opciones investigadas

#### 1. `x_vector_only_mode=True` — Timbre solo (rápido de probar)
- Extrae solo el `ref_spk_embedding` y descarta `ref_code`
- El modelo genera con fonética/prosodia nativa del idioma destino + timbre del hablante
- API oficial lo soporta: `create_voice_clone_prompt(..., x_vector_only_mode=True)`
- **Acción:** Agregar parámetro `x_vector_only_mode` al endpoint `POST /v1/audio/voice-clone/generate`
- **Prioridad:** Alta | **Esquema:** fácil

#### 2. Prompt híbrido manual (experimental)
- Construir un `VoiceClonePromptItem` con:
  - `ref_spk_embedding` de la voz del usuario (timbre)
  - `ref_code` de un hablante nativo del idioma destino (prosodia/fonética)
- No está soportado oficialmente por la API; puede sonar bien o raro
- **Acción:** Implementar endpoint de prueba `/v1/audio/voice-clone/hybrid`
- **Prioridad:** Media | **Esquema:** experimental

#### 3. Fine-tuning con audio del hablante en inglés (mejor calidad)
- Grabar 30–60 min de la persona hablando en inglés
- Fine-tuning SFT del modelo Base (`Qwen/Qwen3-TTS-12Hz-1.7B-Base`)
- El modelo aprende timbre + fonética inglesa del hablante juntas
- Requiere GPU y dataset curado
- **Acción:** Agregar documentación/scripts de fine-tuning al repo
- **Prioridad:** Alta | **Esquema:** complejo

#### 4. Workflow Voice Design → Clone (compromiso rápido)
- Usar VoiceDesign para generar una referencia en inglés con características similares
- Clonar desde esa referencia con `create_voice_clone_prompt`
- Pierde fidelidad exacta al hablante original pero la pronunciación es perfecta
- **Acción:** Documentar workflow en la API docs
- **Prioridad:** Baja | **Esquema:** medio

---

## Fine-tuning general

El modelo Base (`Qwen3-TTS-12Hz-1.7B-Base`) soporta fine-tuning de un solo hablante. La guía oficial está en:
https://github.com/QwenLM/Qwen3-TTS/tree/main/finetuning

### Pasos del fine-tuning oficial

1. **Dataset JSONL:**
   ```jsonl
   {"audio":"./data/utt0001.wav","text":"Hello world","ref_audio":"./data/ref.wav"}
   ```

2. **Extraer audio_codes:**
   ```bash
   python prepare_data.py \
     --device cuda:0 \
     --tokenizer_model_path Qwen/Qwen3-TTS-Tokenizer-12Hz \
     --input_jsonl train_raw.jsonl \
     --output_jsonl train_with_codes.jsonl
   ```

3. **SFT:**
   ```bash
   python sft_12hz.py \
     --init_model_path Qwen/Qwen3-TTS-12Hz-1.7B-Base \
     --output_model_path output \
     --train_jsonl train_with_codes.jsonl \
     --batch_size 32 --lr 2e-6 --num_epochs 10 \
     --speaker_name mi_voz
   ```

**Acción:** Agregar endpoint o script para cargar modelos fine-tuneados personalizados en el server.
**Prioridad:** Media

---

## Otras mejoras pendientes

| # | Mejora | Prioridad | Estado |
|---|--------|-----------|--------|
| 1 | Pre-descarga de modelos con hf_transfer + resume | Alta | ✅ Implementado en PR #1 |
| 2 | Soporte de mirrors via HF_ENDPOINT | Alta | ✅ Implementado en PR #1 |
| 3 | Parámetro `x_vector_only_mode` en voice-clone | Alta | 🔄 Pendiente |
| 4 | Scripts/documentación de fine-tuning | Media | 🔄 Pendiente |
| 5 | Endpoint de prompt híbrido (cross-lingual) | Media | 🔄 Pendiente |
| 6 | Workflow Voice Design → Clone documentado | Baja | 🔄 Pendiente |
