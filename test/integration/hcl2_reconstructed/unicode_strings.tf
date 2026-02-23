locals {
  basic_unicode   = "Hello, 世界! こんにちは Привет नमस्ते"
  unicode_escapes = "© ♥ ♪ ☠ ☺"
  emoji_string    = "🚀 🌍 🔥 🎉"
  rtl_text        = "English and العربية text mixed"
  complex_unicode = "Python (파이썬) es 很棒的! ♥ αβγδ"
  ascii           = "ASCII: abc123"
  emoji           = "Emoji: 🚀🌍🔥🎉"
  math            = "Math: ∑∫√∞≠≤≥"
  currency        = "Currency: £€¥₹₽₩"
  arrows          = "Arrows: ←↑→↓↔↕"
  cjk             = "CJK: 你好世界안녕하세요こんにちは"
  cyrillic        = "Cyrillic: Привет мир"
  special         = "Special: ©®™§¶†‡"
  mixed_content   = <<-EOT
    Line with interpolation: ${var.name}
    Line with emoji: 👨‍👩‍👧‍👦
    Line with quotes: "quoted text"
    Line with backslash: \escaped
  EOT
}
