#!/bin/sh

# You may need install arm-trusted-firmware-tools for fiptool
# If you want to compile for en7523, you need install gcc-arm-linux-gnueabi toolchain

# Auto-selected by SOC below unless TOOLCHAIN is explicitly provided
TOOLCHAIN=${TOOLCHAIN:-}
LZMA_COMPRESS=${LZMA_COMPRESS:-0}
VERSION=${VERSION:-2025}
LOCAL_FIPTOOL=/tools/fiptool/fiptool

die()
{
	echo "Error: $*"
	exit 1
}

lzma_compress()
{
	SRC="$1"
	DST="$2"

	[ -f "$SRC" ] || return 1
	rm -f "$DST"

	# Preferred path: xz with explicit lzma container
	if command -v xz >/dev/null 2>&1; then
		xz --format=lzma --stdout "$SRC" > "$DST" 2>/dev/null && return 0
		rm -f "$DST"
	fi

	# OpenWrt host-tools style: lzma e <src> <dst>
	if command -v lzma >/dev/null 2>&1; then
		lzma e "$SRC" "$DST" >/dev/null 2>&1 && return 0
		rm -f "$DST"

		# xz-lzma/busybox style: stream to stdout
		lzma -z -c "$SRC" > "$DST" 2>/dev/null && return 0
		rm -f "$DST"
	fi

	return 1
}

if [ "$VERSION" = "2025" ]; then
    UBOOT_DIR=uboot-mtk-20250711
else
    die "Unsupported VERSION. Please specify VERSION=2026."
fi

if [ -z "$SOC" ] || [ -z "$BOARD" ]; then
	echo "Usage: SOC=<en7523|an7552|an7581|an7583> BOARD=<evb|w1700k> VERSION=2026 $0"
	echo "eg: SOC=en7523 BOARD=evb $0"
	echo "eg: SOC=an7581 BOARD=evb VERSION=2026 $0"
	exit 1
fi

# Airoha platform target mapping (aligned with OpenWrt Makefile behavior)
case "${SOC}_${BOARD}" in
	en7523_evb |\
	an7552_evb |\
	an7581_evb |\
	an7583_evb)
		UBOOT_CFG="${SOC}_${BOARD}_defconfig"
		UBOOT_IMAGE="u-boot.fip"
		BL2_IMAGE="${SOC}-bl2.bin"
		BL31_IMAGE="${SOC}-bl31.bin"
		BL_SOC_DIR="${SOC}"
		OUTPUT_PREFIX="${SOC}-u-boot-${BOARD}-${VERSION}"
		;;
	*)
		UBOOT_CFG="${SOC}_${BOARD}_defconfig"
		UBOOT_IMAGE="u-boot.bin"
		BL_SOC_DIR="${SOC}"
		OUTPUT_PREFIX="${SOC}-u-boot-${BOARD}-${VERSION}"
		;;
esac

# Auto-select cross toolchain by SOC when TOOLCHAIN is not provided
if [ -z "$TOOLCHAIN" ]; then
	case "$SOC" in
		en7523|an7552)
			# EN7523 is ARMv7 (32-bit)
			TOOLCHAIN="arm-linux-gnueabi-"
			;;
		an7581|an7583)
			TOOLCHAIN="aarch64-linux-gnu-"
			;;
		*)
			die "Unsupported SOC '$SOC'"
			;;
	esac
fi

echo "======================================================================"
echo "Checking environment..."
echo "======================================================================"

echo "Selected toolchain: ${TOOLCHAIN}"

# Check if Python is installed on the system
command -v python3 >/dev/null 2>&1
if [ "$?" != "0" ]; then
	die "Python is not installed on this system."
fi

echo "Trying cross compiler..."
command -v "${TOOLCHAIN}gcc" >/dev/null 2>&1
if [ "$?" != "0" ]; then
	die "${TOOLCHAIN}gcc not found!"
fi

if [ "$UBOOT_IMAGE" = "u-boot.fip" ] || [ "$LZMA_COMPRESS" = "1" ]; then
	if ! command -v lzma >/dev/null 2>&1 && ! command -v xz >/dev/null 2>&1; then
		die "Neither lzma nor xz tool found"
	fi
fi

if [ "$UBOOT_IMAGE" = "u-boot.fip" ]; then
	if [ -x "$LOCAL_FIPTOOL" ]; then
		FIPTOOL_BIN="$LOCAL_FIPTOOL"
		echo "Using local fiptool: $FIPTOOL_BIN"
	elif command -v fiptool >/dev/null 2>&1; then
		FIPTOOL_BIN="fiptool"
	else
		die "fiptool not found (checked: $LOCAL_FIPTOOL and PATH)"
	fi
	echo "fiptool found, help: $($FIPTOOL_BIN --help | head -n1)"
fi

echo "======================================================================"
echo "Configuration:"
echo "======================================================================"

echo "VERSION: $VERSION"
echo "SOC: $SOC"
echo "BOARD: $BOARD"
echo "U-Boot Dir: $UBOOT_DIR"
echo "U-Boot Config: $UBOOT_CFG"
echo "U-Boot Image: $UBOOT_IMAGE"
echo "BL2 Image: $BL2_IMAGE"
echo "BL31 Image: $BL31_IMAGE"
echo "Toolchain Prefix: $TOOLCHAIN"
echo "LZMA Compress: $LZMA_COMPRESS"
echo "Output Prefix: $OUTPUT_PREFIX"

if [ ! -d "$UBOOT_DIR" ]; then
	die "U-Boot directory '$UBOOT_DIR' not found!"
fi

if [ ! -f "$UBOOT_DIR/configs/$UBOOT_CFG" ]; then
	die "U-Boot config '$UBOOT_CFG' not found in $UBOOT_DIR/configs/"
fi

if [ "$UBOOT_IMAGE" = "u-boot.fip" ]; then
	BL2_PATH="$UBOOT_DIR/board/airoha/$BL_SOC_DIR/$BL2_IMAGE"
	BL31_PATH="$UBOOT_DIR/board/airoha/$BL_SOC_DIR/$BL31_IMAGE"
	[ -f "$BL2_PATH" ] || die "BL2 image not found: $BL2_PATH"
	[ -f "$BL31_PATH" ] || die "BL31 image not found: $BL31_PATH"
fi

if command -v nproc >/dev/null 2>&1; then
	JOBS=$(nproc)
else
	JOBS=1
fi

echo "======================================================================"
echo "Build u-boot..."
echo "======================================================================"

echo "Build u-boot..."
rm -f "$UBOOT_DIR/u-boot.bin" "$UBOOT_DIR/u-boot.bin.lzma" "$UBOOT_DIR/u-boot.fip" "$UBOOT_DIR/bl2.fip" "$UBOOT_DIR/bl31.bin.lzma"
cp -f "$UBOOT_DIR/configs/$UBOOT_CFG" "$UBOOT_DIR/.config"

make -C "$UBOOT_DIR" olddefconfig

# Align with OpenWrt package config tweak
sed -i 's/CONFIG_TOOLS_LIBCRYPTO=y/# CONFIG_TOOLS_LIBCRYPTO is not set/' "$UBOOT_DIR/.config"

make -C "$UBOOT_DIR" clean
make -C "$UBOOT_DIR" CROSS_COMPILE="${TOOLCHAIN}" STAGING_DIR="${Staging}" -j "$JOBS" all

if [ -f "$UBOOT_DIR/u-boot.bin" ]; then
	echo "u-boot build done!"
else
	die "u-boot build fail!"
fi

if [ "$LZMA_COMPRESS" = "1" ]; then
	lzma_compress "$UBOOT_DIR/u-boot.bin" "$UBOOT_DIR/u-boot.bin.lzma" || die "lzma compress u-boot.bin failed"
fi

if [ "$UBOOT_IMAGE" = "u-boot.fip" ]; then
	if [ "$LZMA_COMPRESS" = "1" ]; then
		lzma_compress "$BL31_PATH" "$UBOOT_DIR/bl31.bin.lzma" || die "lzma compress bl31 failed"
		SOC_FW="$UBOOT_DIR/bl31.bin.lzma"
		NT_FW="$UBOOT_DIR/u-boot.bin.lzma"
	else
		SOC_FW="$BL31_PATH"
		NT_FW="$UBOOT_DIR/u-boot.bin"
	fi

	"$FIPTOOL_BIN" create \
		--tb-fw "$BL2_PATH" \
		"$UBOOT_DIR/bl2.fip" || die "create bl2.fip failed"

	"$FIPTOOL_BIN" create \
		--soc-fw "$SOC_FW" \
		--nt-fw "$NT_FW" \
		"$UBOOT_DIR/u-boot.fip" || die "create u-boot.fip failed"
fi

echo "======================================================================"
echo "Copying output files..."
echo "======================================================================"

mkdir -p "output_airoha"

if [ "$UBOOT_IMAGE" = "u-boot.fip" ]; then
	[ -f "$UBOOT_DIR/bl2.fip" ] || die "bl2.fip not generated"
	[ -f "$UBOOT_DIR/u-boot.fip" ] || die "u-boot.fip not generated"
	MD5_BL2=$(md5sum "$UBOOT_DIR/bl2.fip" | awk '{print $1}')
	MD5_BL31=$(md5sum "$UBOOT_DIR/u-boot.fip" | awk '{print $1}')
	echo "BL2 fip ${SOC} ${BOARD} ${VERSION} build done!" 
	echo "BL2 fip md5: $MD5_BL2"
	echo "BL31+u-boot fip ${SOC} ${BOARD} ${VERSION} build done!"
	echo "BL31+u-boot fip md5: $MD5_BL31"
	cp -f "$UBOOT_DIR/bl2.fip" "output_airoha/${OUTPUT_PREFIX}_md5-${MD5_BL2}-bl2.fip"
	cp -f "$UBOOT_DIR/u-boot.fip" "output_airoha/${OUTPUT_PREFIX}_md5-${MD5_BL31}-bl31-u-boot.fip"
	echo "${OUTPUT_PREFIX} build done"
	echo "Output: output_airoha/${OUTPUT_PREFIX}_md5-${MD5_BL2}-bl2.fip"
	echo "Output: output_airoha/${OUTPUT_PREFIX}_md5-${MD5_BL31}-bl31-u-boot.fip"
else
	if [ "$LZMA_COMPRESS" = "1" ]; then
		[ -f "$UBOOT_DIR/u-boot.bin.lzma" ] || die "u-boot.bin.lzma not generated"
		MD5_UBOOT=$(md5sum "$UBOOT_DIR/u-boot.bin.lzma" | awk '{print $1}')
		echo "u-boot ${SOC} ${BOARD} ${VERSION} build done!"
		echo "u-boot md5: $MD5_UBOOT"
		cp -f "$UBOOT_DIR/u-boot.bin.lzma" "output_airoha/${OUTPUT_PREFIX}_md5-${MD5_UBOOT}.bin.lzma"
		echo "${OUTPUT_PREFIX} build done"
		echo "Output: output_airoha/${OUTPUT_PREFIX}_md5-${MD5_UBOOT}.bin.lzma"
	else
		[ -f "$UBOOT_DIR/u-boot.bin" ] || die "u-boot.bin not generated"
		echo "u-boot ${SOC} ${BOARD} ${VERSION} build done!"
		MD5_UBOOT=$(md5sum "$UBOOT_DIR/u-boot.bin" | awk '{print $1}')
		echo "u-boot md5: $MD5_UBOOT"
		cp -f "$UBOOT_DIR/u-boot.bin" "output_airoha/${OUTPUT_PREFIX}_md5-${MD5_UBOOT}.bin"
		echo "${OUTPUT_PREFIX} build done"
		echo "Output: output_airoha/${OUTPUT_PREFIX}_md5-${MD5_UBOOT}.bin"
	fi

	if [ -f "$UBOOT_DIR/u-boot.dtb" ]; then
		echo "u-boot dtb found, copying to output"
		MD5_DTB=$(md5sum "$UBOOT_DIR/u-boot.dtb" | awk '{print $1}')
		echo "u-boot dtb md5: $MD5_DTB"
		cp -f "$UBOOT_DIR/u-boot.dtb" "output_airoha/${OUTPUT_PREFIX}_md5-${MD5_DTB}.dtb"
		echo "Output: output_airoha/${OUTPUT_PREFIX}_md5-${MD5_DTB}.dtb"
	fi
fi