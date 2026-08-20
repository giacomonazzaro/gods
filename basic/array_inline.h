#pragma once

#include <basic/array.h>

#include <cassert>
#include <cstdlib>
#include <cstring>
#include <initializer_list>
#include <type_traits>
#include <vector>

// An array that stores up to N elements inline and spills everything to the
// heap if it grows beyond N (leaving inline storage unused). Restricted to
// trivially-copyable elements, so copies are plain memory moves.
//
// The inline elements and the heap pointer are never both in use, so they
// share their bytes: an array that fits inline pays nothing for the pointer.
// `count` says which of the two is live, in its top bit — the sign would not
// do, because -0 and 0 are the same number and "on the heap, empty" needs to
// be tellable from "inline, empty".
//
// The capacity has no field of its own either. Inline it is always N; on the
// heap it is written into the front of the allocation, in front of the
// elements.
//
// Implicitly converts to `array<T>` (a non-owning span), so functions can take
// `array<const T>` parameters and accept both Array_Inline and std::vector.
template <class T, int N>
struct Array_Inline {
  static_assert(
    std::is_trivially_copyable<T>::value,
    "Array_Inline requires a trivially-copyable element type"
  );
  static_assert(
    alignof(T) <= alignof(T*),
    "Array_Inline requires an element no more aligned than a pointer"
  );

  // Set in `count` while the elements live on the heap.
  static constexpr int HEAP_FLAG = 1 << 30;
  // Bytes kept in front of a heap allocation to hold its capacity. A whole
  // pointer's worth, so the elements behind it stay aligned.
  static constexpr int HEAP_HEADER = (int)sizeof(T*);

  // The pointer carries the initializer, not the elements: an element type
  // with default member initializers of its own (Turn_Action has them) would
  // otherwise delete the union's default constructor. The elements start
  // unset, as they always did — `count` says how many of them are real.
  union {
    T  inline_storage[N];
    T* heap_items = nullptr;
  };
  int count = 0;

  // Written out rather than defaulted: an element type with default member
  // initializers of its own (Turn_Action has them) gives the array of
  // elements a non-trivial default constructor, and a union with such a
  // member has no default constructor of its own.
  Array_Inline() {}
  Array_Inline(const Array_Inline& other) { copy_from(other); }
  // Construct from an Array_Inline of any capacity (copies the live
  // elements).
  template <int M>
  Array_Inline(const Array_Inline<T, M>& other) {
    assign(other.begin(), other.end());
  }
  // Construct from a std::vector, for call sites that still produce one.
  Array_Inline(const std::vector<T>& other) {
    assign(other.begin(), other.end());
  }
  // Construct from a braced list, e.g. Array_Inline<const char*, N>{"a",
  // "b"}.
  Array_Inline(std::initializer_list<T> list) {
    assign(list.begin(), list.end());
  }
  Array_Inline& operator=(const Array_Inline& other) {
    if (this != &other) {
      release();
      copy_from(other);
    }
    return *this;
  }
  // Assign from an Array_Inline of any capacity (copies the live elements).
  template <int M>
  Array_Inline& operator=(const Array_Inline<T, M>& other) {
    assign(other.begin(), other.end());
    return *this;
  }
  // Assign from a std::vector or an array (span) view, for convenience.
  Array_Inline& operator=(const std::vector<T>& other) {
    assign(other.begin(), other.end());
    return *this;
  }
  // Assign from a braced list, e.g. targets = {"Ok"}.
  Array_Inline& operator=(std::initializer_list<T> list) {
    assign(list.begin(), list.end());
    return *this;
  }
  template <class U>
  Array_Inline& operator=(const array<U>& other) {
    assign(other.begin(), other.end());
    return *this;
  }
  ~Array_Inline() { release(); }

  bool on_heap() const { return (count & HEAP_FLAG) != 0; }
  int  size() const { return count & ~HEAP_FLAG; }
  bool empty() const { return size() == 0; }
  void clear() { set_size(0); }
  int  capacity() const { return on_heap() ? heap_capacity(heap_items) : N; }

  T*       items() { return on_heap() ? heap_items : inline_storage; }
  const T* items() const { return on_heap() ? heap_items : inline_storage; }

  T&       operator[](int index) { return items()[index]; }
  const T& operator[](int index) const { return items()[index]; }
  T&       back() { return items()[size() - 1]; }
  const T& back() const { return items()[size() - 1]; }
  T&       front() { return items()[0]; }
  const T& front() const { return items()[0]; }

  T*       begin() { return items(); }
  T*       end() { return items() + size(); }
  const T* begin() const { return items(); }
  const T* end() const { return items() + size(); }
  T*       data() { return items(); }
  const T* data() const { return items(); }

  void push_back(const T& value) {
    const int used = size();
    if (used == capacity()) grow();
    items()[used] = value;
    set_size(used + 1);
  }
  void pop_back() {
    assert(size() > 0);
    set_size(size() - 1);
  }

  // Replace the contents with the range [first, last).
  template <class Iterator>
  void assign(Iterator first, Iterator last) {
    set_size(0);
    for (Iterator it = first; it != last; ++it) push_back(*it);
  }

  template <class Iterator>
  void append(Iterator first, Iterator last) {
    for (Iterator it = first; it != last; ++it) push_back(*it);
  }

  // Erase one element, shifting the tail down. Returns the next position.
  T* erase(T* position) {
    for (T* p = position; p + 1 != end(); ++p) {
      *p = *(p + 1);
    }
    set_size(size() - 1);
    return position;
  }

  // Non-owning views (spans) over the live elements.
  operator array<T>() { return array<T>(items(), (size_t)size()); }
  operator array<const T>() const {
    return array<const T>(items(), (size_t)size());
  }

 private:
  // The capacity written in front of a heap allocation. memcpy rather than a
  // cast, so it does not matter how T is aligned.
  static int heap_capacity(const T* items) {
    int stored = 0;
    std::memcpy(&stored, (const char*)items - HEAP_HEADER, sizeof(int));
    return stored;
  }
  static T* heap_allocate(int capacity) {
    char* block = (char*)std::malloc(
      (size_t)HEAP_HEADER + sizeof(T) * (size_t)capacity
    );
    std::memcpy(block, &capacity, sizeof(int));
    return (T*)(block + HEAP_HEADER);
  }
  static void heap_free(T* items) { std::free((char*)items - HEAP_HEADER); }

  // Keeps the flag that says where the elements are.
  void set_size(int new_size) { count = new_size | (count & HEAP_FLAG); }

  void grow() {
    const int used         = size();
    const int new_capacity = capacity() * 2;
    T*        heap         = heap_allocate(new_capacity);
    std::memcpy(heap, items(), sizeof(T) * (size_t)used);
    if (on_heap()) heap_free(heap_items);
    heap_items = heap;
    count      = used | HEAP_FLAG;
  }
  void release() {
    if (on_heap()) heap_free(heap_items);
    count = 0;
  }
  void copy_from(const Array_Inline& other) {
    const int used = other.size();
    if (used <= N) {
      std::memcpy(inline_storage, other.items(), sizeof(T) * (size_t)used);
      count = used;
    } else {
      heap_items = heap_allocate(used);
      std::memcpy(heap_items, other.items(), sizeof(T) * (size_t)used);
      count = used | HEAP_FLAG;
    }
  }
};
