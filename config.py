"""
Configurações do Radar de Leilões.

Este é o único arquivo que você precisa mexer para mudar o comportamento:
cidades, valor máximo, palavras-chave etc.
"""

# ⚠️ VALOR_MAXIMO e TIPOS_ALERTA são só os valores INICIAIS dos avisos.
# Depois que você usa comandos no chat do bot (/tipos, /preco...), quem manda
# é o arquivo filtros.json. Para voltar a estes valores, mande /padrao no chat.

# Valor máximo de lance (em R$) para receber alerta no Telegram.
# Lotes mais caros continuam aparecendo no site, só não geram aviso.
VALOR_MAXIMO = 6000

# Que tipos de veículo geram aviso no Telegram. Opções:
#   "Moto", "Carro", "Caminhonete/Utilitário", "Caminhão/Ônibus",
#   "Reboque/Outros", "Leilão de prefeitura"
# Ex.: TIPOS_ALERTA = ["Moto", "Carro"]
TIPOS_ALERTA = ["Moto", "Leilão de prefeitura"]

# Cidades da região (de Foz do Iguaçu até Cascavel).
# Pode escrever com ou sem acento, maiúscula ou minúscula: o sistema normaliza.
CIDADES = [
    "Foz do Iguaçu",
    "Santa Terezinha de Itaipu",
    "São Miguel do Iguaçu",
    "Itaipulândia",
    "Medianeira",
    "Missal",
    "Serranópolis do Iguaçu",
    "Matelândia",
    "Ramilândia",
    "Céu Azul",
    "Vera Cruz do Oeste",
    "Santa Tereza do Oeste",
    "Cascavel",
    "Santa Helena",
    "Diamante d'Oeste",
    # "Toledo",   # tire o # do começo da linha para incluir
]

# Na Receita Federal, o pátio às vezes vem com um apelido em vez do nome da
# cidade (ex.: "FOZ VEÍCULOS", "DVA 1 - CASCAVEL"). Estes pedaços de texto
# também contam como "está na região". Formato: "pedaço do texto": "cidade".
APELIDOS_PATIO = {
    "FOZ": "Foz do Iguaçu",
    "CASCAVEL": "Cascavel",
}

# Palavras que fazem um leilão de prefeitura (PNCP) ser considerado
# interessante. Prefeitura quase nunca detalha o lote no título, então
# o filtro é mais aberto: o alerta pede para você abrir o edital.
PALAVRAS_PREFEITURA = ["VEIC", "MOTO", "BENS MOVEIS", "INSERVIV", "SUCATA"]

# Endereço do site (vai no link do /lista do Telegram).
SITE = "https://default138.github.io/radar-leiloes/"

# Só avisa no Telegram que uma fonte deu erro depois de tantas coletas
# seguidas com erro (2 = um dia inteiro). Bloqueios passageiros não incomodam.
FALHAS_PARA_AVISAR = 2

# Quantos dias antes do leilão mandar o lembrete no Telegram.
DIAS_LEMBRETE = 1

# Pausa (segundos) entre requisições, para não sobrecarregar os sites.
PAUSA_ENTRE_REQUISICOES = 0.5
