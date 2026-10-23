# Vídeo Lab IA — versões

Versões prontas do **Vídeo Lab IA** (antes chamado Enxuto IA): conversão, compressão e edição de vídeos diretamente no
seu computador. Desenvolvido por RLA.dev. Versão atual: **1.35.17**.

- [`Vídeo Lab IA.zip`](https://github.com/rla-devv/VideoLabIA-versoes/raw/main/V%C3%ADdeo%20Lab%20IA.zip) — para instalar no
  Windows: descompacte ("Extrair tudo") e dê dois cliques em "Instalar Vídeo Lab IA" (não precisa ter o Python: ele baixa
  um só para o app). As atualizações chegam depois pelo aviso dentro do app. Este arquivo fica sempre aqui, com este
  nome: é o que o site baixa.
- [Releases](https://github.com/rla-devv/VideoLabIA-versoes/releases) — uma por versão (`vX.Y.Z`), com o instalador e os
  arquivos que a instalação e a atualização baixam. Servem para contar os downloads de cada versão, de forma anônima.
- [`Vídeo Lab IA.html`](https://github.com/rla-devv/VideoLabIA-versoes/raw/main/V%C3%ADdeo%20Lab%20IA.html) — o app num arquivo
  só, para usar sem instalar: abra no Google Chrome ou no Microsoft Edge. Ele também avisa quando há versão nova.
- `atualizacao.json` — a versão mais recente: número, novidades e cada arquivo com SHA-256, tamanho e endereço na Release.
  É o que o aviso de atualização consulta. `release.json` é a lista de arquivos da Release mais recente.
- `versoes/` — a página de cada versão publicada. Para voltar a uma versão anterior, abra o arquivo dela.
- `ia/` — as bibliotecas e o modelo de detecção de rostos e de reconhecimento de voz (MediaPipe e Transformers.js, licença
  Apache 2.0), que o app instalado baixa uma vez e confere pelo SHA-256.

Este repositório se chamava `enxuto-versoes`; o endereço antigo continua levando para cá, e é por ele que as instalações
antigas recebem as atualizações. Alguns nomes antigos ficam aqui de propósito, pelo mesmo motivo: os arquivos
`versoes/Enxuto-X.Y.Z.html` e as cópias `Vídeo Lab.zip`, `Enxuto IA.zip` e `Enxuto.zip` (iguais ao `Vídeo Lab IA.zip`,
para os links antigos).

Nenhum vídeo é enviado para a internet: tudo roda no seu computador.

Este repositório guarda só as versões prontas, geradas pelo `publicar.py` do código-fonte.
