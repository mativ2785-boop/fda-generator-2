"""
compress_pdf.py
Comprime un PDF al tamaño mínimo sin pérdida de contenido.
Estrategia en dos pasos:
  1. pikepdf  — recomprime streams y elimina objetos no usados
  2. ghostscript — recomprime imágenes a 150 DPI (calidad ebook)

Uso:
    python3 compress_pdf.py input.pdf output.pdf

Dependencias:
    pip install pikepdf --break-system-packages
    apt-get install ghostscript   (o brew install ghostscript en Mac)
"""
import sys
import os
import subprocess
import shutil
import tempfile

def compress_with_pikepdf(input_path: str, output_path: str) -> int:
    """Paso 1: recomprimir streams con pikepdf."""
    import pikepdf
    pdf = pikepdf.open(input_path)
    pdf.save(
        output_path,
        compress_streams=True,
        stream_decode_level=pikepdf.StreamDecodeLevel.generalized,
        object_stream_mode=pikepdf.ObjectStreamMode.generate,
        normalize_content=False,
        linearize=True,
        recompress_flate=True,
    )
    return os.path.getsize(output_path)


def compress_with_ghostscript(input_path: str, output_path: str,
                               image_dpi: int = 150) -> int:
    """
    Paso 2: recomprimir imágenes con ghostscript.
    image_dpi=150 es suficiente para lectura en pantalla y buena impresión.
    Subir a 200 si se necesita mayor calidad de imagen.
    """
    cmd = [
        'gs',
        '-sDEVICE=pdfwrite',
        '-dCompatibilityLevel=1.5',
        '-dPDFSETTINGS=/ebook',
        '-dNOPAUSE', '-dQUIET', '-dBATCH',
        '-dCompressFonts=true',
        '-dSubsetFonts=true',
        '-dDetectDuplicateImages=true',
        f'-dColorImageResolution={image_dpi}',
        f'-dGrayImageResolution={image_dpi}',
        f'-dMonoImageResolution={image_dpi}',
        f'-sOutputFile={output_path}',
        input_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Ghostscript error:\n{result.stderr}")
    return os.path.getsize(output_path)


def compress(input_path: str, output_path: str, image_dpi: int = 150) -> dict:
    """
    Comprime el PDF en dos pasos y devuelve un dict con los tamaños.
    Si ghostscript no está instalado, usa solo pikepdf.
    """
    orig_size = os.path.getsize(input_path)

    with tempfile.TemporaryDirectory() as tmp:
        step1 = os.path.join(tmp, 'step1.pdf')
        step2 = os.path.join(tmp, 'step2.pdf')

        # Paso 1: pikepdf
        try:
            size_after_pike = compress_with_pikepdf(input_path, step1)
        except ImportError:
            print("⚠️  pikepdf no instalado — saltando paso 1")
            shutil.copy(input_path, step1)
            size_after_pike = orig_size

        # Paso 2: ghostscript
        gs_available = shutil.which('gs') is not None
        if gs_available:
            size_final = compress_with_ghostscript(step1, step2, image_dpi)
            shutil.copy(step2, output_path)
        else:
            print("⚠️  ghostscript no instalado — usando solo pikepdf")
            shutil.copy(step1, output_path)
            size_final = size_after_pike

    reduction = (1 - size_final / orig_size) * 100

    return {
        'original_mb':   round(orig_size   / 1048576, 2),
        'final_mb':      round(size_final  / 1048576, 2),
        'reduction_pct': round(reduction, 1),
    }


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Uso: python3 compress_pdf.py input.pdf output.pdf [dpi]")
        print("  dpi  — resolución de imágenes (default: 150)")
        sys.exit(1)

    inp = sys.argv[1]
    out = sys.argv[2]
    dpi = int(sys.argv[3]) if len(sys.argv) > 3 else 150

    if not os.path.exists(inp):
        print(f"Error: no existe {inp}")
        sys.exit(1)

    print(f"Comprimiendo {inp} ...")
    stats = compress(inp, out, image_dpi=dpi)
    print(f"Original:   {stats['original_mb']} MB")
    print(f"Final:      {stats['final_mb']} MB")
    print(f"Reducción:  {stats['reduction_pct']}%")
    print(f"✅ Guardado en {out}")
