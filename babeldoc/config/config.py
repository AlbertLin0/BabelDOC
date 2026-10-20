from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from typing import Any


@dataclass
class OpenAIConfig:
    model: str = "gpt-4o-mini"
    base_url: str | None = None
    api_key: str | None = None
    term_extraction_model: str | None = None
    term_extraction_base_url: str | None = None
    term_extraction_api_key: str | None = None
    enable_json_mode_if_requested: bool = False
    send_dashscope_header: bool = False
    send_temperature: bool = True
    reasoning: str | None = None
    thinking: str | None = None
    term_extraction_reasoning: str | None = None


@dataclass
class BabelDocConfig:
    files: list[str] = field(default_factory=list)
    debug: bool = False
    warmup: bool = False
    rpc_doclayout: str | None = None
    rpc_doclayout2: str | None = None
    rpc_doclayout3: str | None = None
    rpc_doclayout4: str | None = None
    rpc_doclayout5: str | None = None
    rpc_doclayout6: str | None = None
    rpc_doclayout7: str | None = None
    generate_offline_assets: str | None = None
    restore_offline_assets: str | None = None
    working_dir: str | None = None
    metadata_extra_data: str | None = None
    enable_process_pool: bool = False
    pages: str | None = None
    min_text_length: int = 5
    lang_in: str = "en"
    lang_out: str = "zh"
    output: str | None = None
    qps: int = 4
    ignore_cache: bool = False
    no_dual: bool = False
    no_mono: bool = False
    formular_font_pattern: str | None = None
    formular_char_pattern: str | None = None
    split_short_lines: bool = False
    short_line_split_factor: float = 0.8
    skip_clean: bool = False
    dual_translate_first: bool = False
    disable_rich_text_translate: bool = False
    enhance_compatibility: bool = False
    use_alternating_pages_dual: bool = False
    watermark_output_mode: str = "watermarked"
    max_pages_per_part: int | None = None
    no_watermark: bool = False
    report_interval: float = 0.1
    translate_table_text: bool = False
    show_char_box: bool = False
    skip_scanned_detection: bool = False
    ocr_workaround: bool = False
    custom_system_prompt: str | None = None
    add_formula_placehold_hint: bool = False
    disable_same_text_fallback: bool = False
    glossary_files: str | None = None
    pool_max_workers: int | None = None
    term_pool_max_workers: int | None = None
    auto_extract_glossary: bool = True
    auto_enable_ocr_workaround: bool = False
    primary_font_family: str | None = None
    only_include_translated_page: bool = False
    save_auto_extracted_glossary: bool = False
    disable_graphic_element_process: bool = False
    merge_alternating_line_numbers: bool = True
    skip_translation: bool = False
    skip_form_render: bool = False
    skip_curve_render: bool = False
    only_parse_generate_pdf: bool = False
    remove_non_formula_lines: bool = False
    non_formula_line_iou_threshold: float = 0.9
    figure_table_protection_threshold: float = 0.9
    skip_formula_offset_calculation: bool = False
    openai: bool = False
    openai_config: OpenAIConfig = field(default_factory=OpenAIConfig)

    def validate(self) -> None:
        if not self.openai:
            raise ValueError("必须选择一个翻译服务：openai=True")
        if self.openai and not self.openai_config.api_key:
            raise ValueError("使用 OpenAI 服务时必须提供 API key")
        if self.watermark_output_mode not in ("watermarked", "no_watermark", "both"):
            raise ValueError(
                f"watermark_output_mode 必须是 'watermarked', 'no_watermark', 'both' 之一，got '{self.watermark_output_mode}'"
            )
        if self.primary_font_family is not None and self.primary_font_family not in (
            "serif",
            "sans-serif",
            "script",
        ):
            raise ValueError(
                f"primary_font_family 必须是 'serif', 'sans-serif', 'script' 之一，got '{self.primary_font_family}'"
            )
        if self.openai_config.thinking is not None and self.openai_config.thinking not in (
            "enabled",
            "disabled",
        ):
            raise ValueError(
                f"openai_config.thinking 必须是 'enabled' 或 'disabled'，got '{self.openai_config.thinking}'"
            )

    @classmethod
    def from_args(cls, args: Any) -> BabelDocConfig:
        openai_config = OpenAIConfig(
            model=args.openai_model,
            base_url=args.openai_base_url,
            api_key=args.openai_api_key,
            term_extraction_model=args.openai_term_extraction_model,
            term_extraction_base_url=args.openai_term_extraction_base_url,
            term_extraction_api_key=args.openai_term_extraction_api_key,
            enable_json_mode_if_requested=args.enable_json_mode_if_requested,
            send_dashscope_header=args.send_dashscope_header,
            send_temperature=not args.no_send_temperature,
            reasoning=args.openai_reasoning,
            thinking=args.openai_thinking,
            term_extraction_reasoning=args.openai_term_extraction_reasoning,
        )
        return cls(
            files=list(args.files) if args.files else [],
            debug=args.debug,
            warmup=args.warmup,
            rpc_doclayout=args.rpc_doclayout,
            rpc_doclayout2=args.rpc_doclayout2,
            rpc_doclayout3=args.rpc_doclayout3,
            rpc_doclayout4=args.rpc_doclayout4,
            rpc_doclayout5=args.rpc_doclayout5,
            rpc_doclayout6=args.rpc_doclayout6,
            rpc_doclayout7=args.rpc_doclayout7,
            generate_offline_assets=args.generate_offline_assets,
            restore_offline_assets=args.restore_offline_assets,
            working_dir=args.working_dir,
            metadata_extra_data=args.metadata_extra_data,
            enable_process_pool=args.enable_process_pool,
            pages=args.pages,
            min_text_length=args.min_text_length,
            lang_in=args.lang_in,
            lang_out=args.lang_out,
            output=args.output,
            qps=args.qps,
            ignore_cache=args.ignore_cache,
            no_dual=args.no_dual,
            no_mono=args.no_mono,
            formular_font_pattern=args.formular_font_pattern,
            formular_char_pattern=args.formular_char_pattern,
            split_short_lines=args.split_short_lines,
            short_line_split_factor=args.short_line_split_factor,
            skip_clean=args.skip_clean,
            dual_translate_first=args.dual_translate_first,
            disable_rich_text_translate=args.disable_rich_text_translate,
            enhance_compatibility=args.enhance_compatibility,
            use_alternating_pages_dual=args.use_alternating_pages_dual,
            watermark_output_mode=args.watermark_output_mode,
            max_pages_per_part=args.max_pages_per_part,
            no_watermark=args.no_watermark,
            report_interval=args.report_interval,
            translate_table_text=args.translate_table_text,
            show_char_box=args.show_char_box,
            skip_scanned_detection=args.skip_scanned_detection,
            ocr_workaround=args.ocr_workaround,
            custom_system_prompt=args.custom_system_prompt,
            add_formula_placehold_hint=args.add_formula_placehold_hint,
            disable_same_text_fallback=args.disable_same_text_fallback,
            glossary_files=args.glossary_files,
            pool_max_workers=args.pool_max_workers,
            term_pool_max_workers=args.term_pool_max_workers,
            auto_extract_glossary=args.auto_extract_glossary,
            auto_enable_ocr_workaround=args.auto_enable_ocr_workaround,
            primary_font_family=args.primary_font_family,
            only_include_translated_page=args.only_include_translated_page,
            save_auto_extracted_glossary=args.save_auto_extracted_glossary,
            disable_graphic_element_process=args.disable_graphic_element_process,
            merge_alternating_line_numbers=args.merge_alternating_line_numbers,
            skip_translation=args.skip_translation,
            skip_form_render=args.skip_form_render,
            skip_curve_render=args.skip_curve_render,
            only_parse_generate_pdf=args.only_parse_generate_pdf,
            remove_non_formula_lines=args.remove_non_formula_lines,
            non_formula_line_iou_threshold=args.non_formula_line_iou_threshold,
            figure_table_protection_threshold=args.figure_table_protection_threshold,
            skip_formula_offset_calculation=args.skip_formula_offset_calculation,
            openai=args.openai,
            openai_config=openai_config,
        )