# Contributing to Bumble BLE Testing Framework

Thank you for your interest in contributing! This document provides guidelines for contributing to the project.

## Getting Started

1. Fork the repository
2. Clone your fork
3. Create a virtual environment
4. Install dependencies: `pip install -r requirements.txt`
5. Make your changes
6. Test your changes
7. Submit a pull request

## Code Style

- Follow PEP 8 style guidelines
- Use meaningful variable and function names
- Add docstrings to functions and classes
- Keep lines under 120 characters when reasonable
- Use type hints where appropriate

## Project Structure

```
src/
├── main.py          # Interactive menu (keep UI-focused)
├── scanner.py       # BLE scanning functions
├── connector.py     # Connection/GATT operations
├── hci_snooper.py   # HCI packet capture
└── utils.py         # Shared utilities
```

## Adding New Features

### New Menu Option
1. Add menu item to `print_main_menu()` in `main.py`
2. Create corresponding `async def menu_<feature>()` method
3. Add handler in main menu loop
4. Update README.md with new feature

### New GATT Operation
1. Add method to `BLEConnector` class in `connector.py`
2. Add menu wrapper in `main.py` if interactive
3. Handle errors gracefully
4. Log important events

### New Resource File
1. Add YAML/JSON file to `resources/` directory
2. Update `_load_resource_maps()` if needed
3. Document format in header comment

## Testing

Before submitting:

1. **Manual Testing**
   - Test with real BLE device
   - Verify all menu options work
   - Check error handling

2. **Connection Tests**
   - Scan → Connect → Discover → Read/Write
   - Test bonding and reconnection
   - Test HCI snoop if modified

3. **Cross-Platform** (if possible)
   - Test on Windows
   - Test on Linux
   - Test on macOS

## Commit Guidelines

Use clear, descriptive commit messages:

```
Add burst read operation with interval control

- Implement start_burst_read() in connector
- Add menu option 15
- Add stop command (option 16)
- Update README with burst read docs
```

## Pull Request Process

1. Update documentation (README.md, docstrings)
2. Add your changes to a feature branch
3. Test thoroughly
4. Create pull request with:
   - Clear description of changes
   - Why the change is needed
   - How to test the changes

## Areas for Contribution

### High Priority
- Unit tests for connector and scanner
- Connection stability improvements
- Error handling improvements
- Cross-platform testing

### Medium Priority
- Additional GATT operations
- Configuration file support
- Command-line argument parsing
- Export/import bonding data

### Nice to Have
- GUI interface (optional)
- Scripting/automation mode
- Additional analyzer format support
- Connection profiles/presets

## Bug Reports

Include:
- Python version
- Operating system
- Bluetooth adapter model
- Steps to reproduce
- Expected vs actual behavior
- Relevant logs or error messages

## Questions?

- Open an issue with the "question" label
- Check existing documentation in `docs/`
- Review Bumble documentation

## Code of Conduct

- Be respectful and inclusive
- Welcome newcomers
- Focus on constructive feedback
- Help others learn

## License

By contributing, you agree that your contributions will be licensed under the same license as the project.

---

Thank you for contributing! 🙏
