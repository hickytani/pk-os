"""Regression coverage for boot-critical image partition validation."""

import struct

import pytest

from scripts.assemble_phase2e_disk import (
    EFI_SYSTEM_PARTITION_GUID,
    validate_esp_boot_sector,
)


def make_gpt_image(path, esp_sector):
    sector_size = 512
    entries_lba = 2
    entry_size = 128
    entry_count = 4
    entry_table = bytearray(entry_size * entry_count)
    entry_table[:16] = EFI_SYSTEM_PARTITION_GUID
    struct.pack_into("<Q", entry_table, 32, 2048)
    struct.pack_into("<Q", entry_table, 40, 4095)

    header = bytearray(sector_size)
    header[:8] = b"EFI PART"
    struct.pack_into("<Q", header, 72, entries_lba)
    struct.pack_into("<I", header, 80, entry_count)
    struct.pack_into("<I", header, 84, entry_size)

    with path.open("wb") as image:
        image.truncate(4096 * sector_size)
        image.seek(sector_size)
        image.write(header)
        image.seek(entries_lba * sector_size)
        image.write(entry_table)
        image.seek(2048 * sector_size)
        image.write(esp_sector)


def test_rejects_zero_filled_efi_partition(tmp_path):
    image = tmp_path / "empty-esp.raw"
    make_gpt_image(image, bytes(512))

    with pytest.raises(RuntimeError, match="FAT32 boot sector"):
        validate_esp_boot_sector(image)


def test_accepts_fat32_efi_partition(tmp_path):
    image = tmp_path / "valid-esp.raw"
    boot_sector = bytearray(512)
    boot_sector[82:90] = b"FAT32   "
    boot_sector[510:512] = b"\x55\xaa"
    make_gpt_image(image, boot_sector)

    validate_esp_boot_sector(image)
