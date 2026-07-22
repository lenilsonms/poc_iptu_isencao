import os
import fnmatch
from pathlib import Path

def extrair_conteudo_para_txt(
    raiz: str | Path,
    arquivo_saida: str | Path,
    recursivo: bool = True,
    incluir_ocultos: bool = False,
    extensoes: set[str] | None = None,
    tamanho_max_mb: float | None = None,
    excluir_dirs: set[str] | None = None,  # ex.: {"alembic","logs","**/__pycache__"}
    dry_run: bool = False,                 # se True, só mostra o que seria excluído
) -> None:
    raiz = Path(raiz).resolve()
    arquivo_saida = Path(arquivo_saida)
    if not raiz.is_dir():
        raise NotADirectoryError(f"Diretório inválido: {raiz}")

    # normaliza padrões (POSIX)
    padroes = {p.strip().strip("/").replace("\\", "/") for p in (excluir_dirs or set())}

    def _deve_excluir_dir(rel_path_posix: str, nome: str) -> bool:
        """Match por:
           1) glob no caminho relativo (ex.: **/logs)
           2) nome exato (ex.: logs)
           3) caminho exato relativo (ex.: tests/unit)"""
        for pad in padroes:
            tem_glob = any(ch in pad for ch in "*?")
            if tem_glob and fnmatch.fnmatch(rel_path_posix, pad):
                return True
            if not tem_glob and (nome == pad or rel_path_posix == pad or rel_path_posix.startswith(pad + "/")):
                return True
        return False

    def _parece_texto(p: Path, amostra_bytes: int = 8192) -> bool:
        try:
            with open(p, "rb") as f:
                sample = f.read(amostra_bytes)
        except Exception:
            return False
        if not sample:
            return True
        if b"\x00" in sample:
            return False
        bad = sum(1 for b in sample if (b < 32 and b not in (9, 10, 13)) or b == 127)
        return (bad / len(sample)) < 0.05

    def _ler_com_encoding_robusto(p: Path):
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                with open(p, "r", encoding=enc, errors="strict") as f:
                    for line in f:
                        yield line
                return
            except Exception:
                continue
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                yield line

    if recursivo:
        walker = os.walk(raiz)
    else:
        first = next(os.walk(raiz))
        walker = [first]

    excluidos = []

    arquivos = []
    for dirpath, dirnames, filenames in walker:
        base_rel = Path(dirpath).resolve().relative_to(raiz)
        base_rel_posix = base_rel.as_posix()

        # 1) ocultos
        if not incluir_ocultos:
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]
            filenames = [f for f in filenames if not f.startswith(".")]

        # 2) exclusões
        keep = []
        for d in dirnames:
            rel_dir = (base_rel / d).as_posix() if base_rel_posix else d
            if _deve_excluir_dir(rel_dir, d):
                excluidos.append(rel_dir)
            else:
                keep.append(d)
        dirnames[:] = keep  # impede o walk de descer

        # 3) coleta arquivos
        for nome in filenames:
            p = Path(dirpath) / nome
            arquivos.append(p)

    if dry_run:
        print("Pastas excluídas:")
        for d in sorted(set(excluidos)):
            print(" -", d)
        print(f"\nTotal de arquivos a processar: {len(arquivos)}")
        return

    with open(arquivo_saida, "w", encoding="utf-8") as out:
        out.write(f"# Dump de arquivos — raiz: {raiz}\n\n")
        for arquivo in sorted(arquivos, key=lambda x: x.as_posix().lower()):
            # filtro por extensão
            if extensoes is not None and arquivo.suffix.lower() not in {e.lower() for e in extensoes}:
                continue

            # filtro por tamanho
            if tamanho_max_mb is not None:
                try:
                    if arquivo.stat().st_size > tamanho_max_mb * 1024 * 1024:
                        continue
                except Exception:
                    continue

            if not _parece_texto(arquivo):
                continue

            rel = arquivo.relative_to(raiz).as_posix()
            out.write("\n" + "=" * 80 + "\n")
            out.write(f"ARQUIVO: {rel}\n")
            out.write("=" * 80 + "\n")

            try:
                ultima = "\n"
                for linha in _ler_com_encoding_robusto(arquivo):
                    out.write(linha)
                    ultima = linha
                if not str(ultima).endswith("\n"):
                    out.write("\n")
            except Exception as e:
                out.write(f"\n[ERRO ao ler {rel}: {e}]\n")


extrair_conteudo_para_txt(
    raiz=".",
    arquivo_saida="dump.txt",
    excluir_dirs={"testes_case", "alembic", "logs"},  # nomes exatos na raiz
    dry_run=False        # primeiro rode em modo diagnóstico
)
