/*
 * Minimal flash_table generator for BL2 optimization packaging.
 *
 * Output format:
 *   struct bl2_flash_H {
 *       int flash_entry;
 *       int flash_name_off;
 *       int flash_oob_off;
 *   }
 *   [no entries]
 *
 * This is the smallest valid table layout for parsers that first read header.
 * It is intended for bring-up/testing only.
 */

#include <stdio.h>
#include <stdint.h>
#include <string.h>

#pragma pack(push, 1)
struct bl2_flash_H {
    int32_t flash_entry;
    int32_t flash_name_off;
    int32_t flash_oob_off;
};
#pragma pack(pop)

int main(int argc, char **argv)
{
    const char *out = "flash_table.bin";
    FILE *fp;
    struct bl2_flash_H h;

    if (argc >= 2) {
        out = argv[1];
    }

    fp = fopen(out, "wb");
    if (!fp) {
        perror("fopen");
        return 1;
    }

    memset(&h, 0, sizeof(h));
    h.flash_entry   = 0;
    h.flash_name_off = (int32_t)sizeof(struct bl2_flash_H);
    h.flash_oob_off  = (int32_t)sizeof(struct bl2_flash_H);

    if (fwrite(&h, 1, sizeof(h), fp) != sizeof(h)) {
        perror("fwrite");
        fclose(fp);
        return 2;
    }

    fclose(fp);
    printf("Generated %s (%zu bytes)\n", out, sizeof(h));
    printf("flash_entry=%d, flash_name_off=%d, flash_oob_off=%d\n",
           h.flash_entry, h.flash_name_off, h.flash_oob_off);
    return 0;
}