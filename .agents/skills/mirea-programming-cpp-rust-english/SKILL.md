---
name: mirea-programming-cpp-rust-english
description: Canonical Skill-Textbook for Systems Programming (C++, Rust, Zig) and Technical English terminology. Use when solving MIREA programming assignments, studying low-level memory management, or writing verified systems code.
---

# 🛠️ Скилл-Учебник: Системное Программирование (C++, Rust, Zig) & Technical English

> **Назначение:** Обучающая упряжь (Harness) для TARS и структурированный конспект-учебник для Студента.  
> **Языки:** C++, Rust, Zig + Технический Английский (Technical English).

---

## 🏛️ 1. Фундаментальные Понятия Памяти (Memory Fundamentals)

### 🇬🇧-🇷🇺 Глоссарий Терминов:
| Term (English) | Значение (Русский) | Суть концепта |
|---|---|---|
| **Stack Allocation** | Выделение в Стеке | Быстрая память фиксированного размера, автоматическая очистка при выходе из функции. |
| **Heap Allocation** | Выделение в Куче | Динамическая память произвольного размера (`malloc`/`new`/`box`), требует явного освобождения. |
| **RAII** | Resource Acquisition Is Initialization | Ресурс привязывается к жизни объекта (деструктор автоматизирует очистку в C++). |
| **Borrow Checker** | Компиляторный контролёр заимствований | Механизм Rust, гарантирующий отсутствие Dangle Pointers и Data Races на этапе компиляции. |
| **Explicit Allocator** | Явный Аллокатор | Подход Zig: функции принимают `Allocator` параметром, исключая скрытые аллокации. |

---

## 💻 2. Сравнительный Код-Шаблон: Управление Ресурсом

### C++20 (RAII & Smart Pointers)
```cpp
#include <iostream>
#include <memory>
#include <vector>

class Buffer {
public:
    Buffer(size_t size) : data_(std::make_unique<uint8_t[]>(size)) {
        std::cout << "Buffer allocated on Heap via std::make_unique\n";
    }
    ~Buffer() = default; // Automatic Cleanup via RAII

private:
    std::unique_ptr<uint8_t[]> data_;
};
```

### Rust (Ownership & Move Semantics)
```rust
struct Buffer {
    data: Vec<u8>,
}

impl Buffer {
    fn new(size: usize) -> Self {
        println!("Buffer allocated safely on Heap");
        Self { data: vec![0; size] }
    }
} // Automatically dropped here via Ownership rule
```

### Zig (Explicit Allocator Pattern)
```zig
const std = @import("std");

pub fn main() !void {
    var gpa = std.heap.GeneralPurposeAllocator(.{}){};
    defer _ = gpa.deinit();
    const allocator = gpa.allocator();

    const buffer = try allocator.alloc(u8, 1024);
    defer allocator.free(buffer); // Explicit Deallocation Guarantee
}
```

---

## 📋 3. Чек-Лист Самопроверки для Студента (Self-Assessment Checklist)

- [ ] Понимаю ли я разницу между передачей по значению (`by value`), по ссылке (`by reference`) и по указателю (`by pointer`)?
- [ ] Могу ли я объяснить, почему в Rust запрещены две мутабельные ссылки (`&mut`) на одну область памяти?
- [ ] Знаю ли я, как в C++ избежать утечки памяти при исключении (`std::unique_ptr` vs raw `new`)?
- [ ] Понимаю ли я, как в Zig явный аллокатор помогает находить утечки памяти через `GeneralPurposeAllocator`?

---

## 🤖 4. Правила Интеграции с Google Jules (Git & PR Verification)

1. Все решения задач коммитятся в отдельную ветку `feature/mirea-cpp-rust-lab`.
2. В каждом PR формируется чёткое описание на техническом английском:
   * **Summary**: Goal of assignment
   * **Memory Safety Proof**: Stack vs Heap usage, deallocation checks
   * **Benchmark Results**: Execution speed and footprint.
