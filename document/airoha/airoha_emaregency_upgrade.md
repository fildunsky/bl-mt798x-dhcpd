# Arioha Emergency upgarde by x-modem

## emaregency upgrade with u-boot-2014 without atf formwork

1. push 'reset' button and switch power on

2. set x-modem and key press 'x' to upgrade bootext.ram from sdk

3. upgrade tcboot.bin from serial mode

4. startup to uboot and login by 'telecomadmin/nE7jA%5m' upgrade bootloader by tftp client

read tclinux context from mtd partition

## emaregency upgrade with u-boot-2023

Use the new **bootext.ram** with **emergency_upgrade.bin**.  After the upgrade, it will boot from the
main partition, but there is no kernel, it will stop at uboot to re-flash tclinux.bin or ras.bin.

(**Note: Recommend using the bootext.ram and emergency_upgrade.bin from the SDK release. The SDK u-boot login by "telecomadmin/nE7jA%5m"**)

```shell
$ tftp tcboot.bin

## upgrade kernel and zloader by:
$ tftp tclinux.bin
$ mtd erase tclinux
$ mtd write tclinux 0x81800000 0 0x3700000
```
