import uuid
from shiny import App, Inputs, Outputs, Session, reactive, render, ui
from shiny.types import FileInfo
import pandas as pd
from datetime import datetime, date
import qrcode
from io import BytesIO
import base64
import os
import json
import openpyxl
import hashlib
import urllib.parse 
import crc16
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests
from apscheduler.schedulers.background import BackgroundScheduler
import atexit
import re
from datetime import datetime, timezone, timedelta
from supabase import create_client, Client
import httpx
import time
import threading
import re
import textwrap
from PIL import Image, ImageDraw, ImageFont
import urllib.parse



def hash_senha(senha):
    """Cria hash SHA256 da senha"""
    return hashlib.sha256(senha.encode()).hexdigest()
  
# ==========================================================
# CÓDIGO PIX COPIA E COLA DA EMPRESA (SUBSTITUA PELO SEU!)
# ==========================================================
# Use um leitor de QR code para ler o QR da sua conta e cole o TEXTO aqui
PIX_COPIA_E_COLA_EMPRESA = "00020126580014BR.GOV.BCB.PIX0136f6fb015d-9f27-4bb4-b126-59822ca483ea5204000053039865802BR592559.170.478 CARLOS ALEXAND6009SAO PAULO61080540900062250521aY5uO3lDmsyn3aCaed13x6304C5A9"


import os
from supabase import create_client, Client
import httpx
from datetime import datetime
import time

# ============================================
# CONFIGURAÇÃO DO SUPABASE
# ============================================
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

# ============================================
# CRIAR CLIENTE HTTP CUSTOMIZADO
# ============================================
custom_http_client = httpx.Client(
    http2=False,  # Desabilita HTTP/2
    timeout=httpx.Timeout(30.0, connect=10.0),
    limits=httpx.Limits(
        max_keepalive_connections=5,
        max_connections=10,
        keepalive_expiry=30.0
    ),
    transport=httpx.HTTPTransport(retries=3)
)

# ============================================
# CRIAR CLIENTE SUPABASE
# ============================================
supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_SERVICE_KEY
)

# Substituir o cliente HTTP padrão DEPOIS de criar
supabase.postgrest.session = custom_http_client

print("=" * 60)
print("🔍 VERIFICAÇÃO DE CONFIGURAÇÃO")
print("=" * 60)
print(f"SUPABASE_URL: {'✅ OK' if SUPABASE_URL else '❌ FALTANDO'}   → {SUPABASE_URL}")
print(f"SUPABASE_SERVICE_KEY: {'✅ OK' if SUPABASE_SERVICE_KEY else '❌ FALTANDO'}   → Começa com: {SUPABASE_SERVICE_KEY[:30] if SUPABASE_SERVICE_KEY else 'N/A'}...")
print("=" * 60)
print("✅ Cliente Supabase criado com HTTP/1.1 e retry!")
print("=" * 60)

# ==================== FUNÇÕES AUXILIARES ====================

def validar_cpf(cpf):
    """Valida CPF"""
    cpf = ''.join(filter(str.isdigit, str(cpf)))
    if len(cpf) != 11:
        return False
    # Validação básica (pode melhorar com dígitos verificadores)
    return True

def validar_cnpj(cnpj):
    """Valida CNPJ"""
    cnpj = ''.join(filter(str.isdigit, str(cnpj)))
    if len(cnpj) != 14:
        return False
    return True

def limpar_documento(doc):
    """Remove formatação de CPF/CNPJ"""
    return ''.join(filter(str.isdigit, str(doc)))

def formatar_cpf_cnpj(doc):
    """Formata CPF ou CNPJ automaticamente"""
    if not doc:
        return ""
    doc_limpo = limpar_documento(doc)
    
    if len(doc_limpo) == 11:
        # CPF
        return formatar_cpf(doc_limpo)
    elif len(doc_limpo) == 14:
        # CNPJ
        return formatar_cnpj(doc_limpo)
    else:
        return doc

def formatar_cpf(cpf):
    if not cpf: return ""
    cpf = ''.join(filter(str.isdigit, str(cpf)))
    return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}" if len(cpf) == 11 else cpf

def formatar_cnpj(cnpj):
    if not cnpj: return ""
    cnpj = ''.join(filter(str.isdigit, str(cnpj)))
    return f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}" if len(cnpj) == 14 else cnpj

def formatar_moeda(valor):
    if valor is None: return "R$ 0,00"
    return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def calcular_cashback_progressivo(cliente_id, valor_venda):
    """
    Calcula cashback baseado no nível do cliente
    
    Níveis:
    - Nível 1 PRATA (0-10 compras): 4%
    - Nível 2 OURO (11-25 compras): 5.5%
    - Nível 3 DIAMANTE (26+ compras): 7%
    
    Args:
        cliente_id: ID do cliente
        valor_venda: Valor total da venda
    
    Returns:
        tuple: (valor_cashback, percentual_usado, nivel)
    """
    print(f"\n{'='*60}")
    print(f"🔍 CALCULAR CASHBACK - INICIO")
    print(f"{'='*60}")
    print(f"Cliente ID: {cliente_id}")
    print(f"Valor Venda: R$ {valor_venda:.2f}")
    
    try:
        # Busca número REAL de vendas do cliente direto da tabela vendas
        vendas_result = supabase.table('vendas').select(
            'id', count='exact'
        ).eq('cliente_id', cliente_id).execute()
        
        total_compras = vendas_result.count if vendas_result.count else 0
        
        print(f"📊 Vendas do cliente: {total_compras}")
        print(f"📈 Total de compras REAL do banco: {total_compras}")
        
        # Define percentual baseado em número de compras (3 níveis)
        if total_compras >= 26:
            percentual = 7  # DIAMANTE
            nivel = 3
            nivel_nome = "DIAMANTE 💎"
        elif total_compras >= 11:
            percentual = 5.5  # OURO
            nivel = 2
            nivel_nome = "OURO 🥇"
        else:
            percentual = 4  # PRATA
            nivel = 1
            nivel_nome = "PRATA 🥈"
        
        print(f"🎯 Nível: {nivel} ({nivel_nome}) - {percentual}%")
        
        # Cashback calculado diretamente sobre o valor total da venda
        cashback = valor_venda * (percentual / 100)
        
        print(f"💰 Cashback calculado: R$ {cashback:.2f}")
        print(f"{'='*60}\n")
        
        return cashback, percentual, nivel
        
    except Exception as e:
        print(f"❌ ERRO ao calcular cashback: {e}")
        import traceback
        traceback.print_exc()
        # Retorna 4% mesmo com erro para não perder o cashback
        cashback = valor_venda * 0.04
        print(f"⚠️ Usando 4% padrão: R$ {cashback:.2f}")
        print(f"{'='*60}\n")
        return cashback, 4, 1


def atualizar_nivel_cliente(cliente_id):
    """Atualiza o nível do cliente baseado no total de compras (3 níveis)"""
    try:
        # Busca total de compras
        result = supabase.table('usuarios').select('total_compras').eq('id', cliente_id).execute()
        
        if not result.data:
            return
        
        total_compras = result.data[0].get('total_compras', 0)
        
        # Define nível (3 níveis: Prata, Ouro, Diamante)
        if total_compras >= 26:
            nivel = 3  # DIAMANTE
            nome_nivel = "DIAMANTE 💎"
        elif total_compras >= 11:
            nivel = 2  # OURO
            nome_nivel = "OURO 🥇"
        else:
            nivel = 1  # PRATA
            nome_nivel = "PRATA 🥈"
        
        # Atualiza no banco
        supabase.table('usuarios').update({
            'nivel_cashback': nivel
        }).eq('id', cliente_id).execute()
        
        print(f"✅ Cliente {cliente_id} atualizado para nível {nivel} ({nome_nivel})")
        
    except Exception as e:
        print(f"❌ Erro ao atualizar nível: {e}")


def gerar_numero_venda():
    import random
    return f"VND{datetime.now().strftime('%Y%m%d')}{random.randint(1000, 9999)}"

def gerar_codigo_cliente():
    import random
    import datetime
    codigo = f"CLI{datetime.datetime.now().strftime('%Y%m')}{random.randint(1000, 9999)}"
    print(f"🆔 Código gerado: {codigo}")
    return codigo

def formatar_whatsapp(numero):
    if not numero: return ""
    num = ''.join(filter(str.isdigit, str(numero)))
    if len(num) == 11:
        return f"({num[:2]}) {num[2:7]}-{num[7:]}"
    return numero

def verificar_e_deletar_vendas_expiradas():
    """
    Deleta vendas expiradas com retry robusto
    """
    max_tentativas = 3
    backoff_inicial = 2  # segundos
    
    for tentativa in range(max_tentativas):
        try:
            print(f"🔍 [{datetime.now().strftime('%H:%M:%S')}] Verificando vendas expiradas (tentativa {tentativa + 1}/{max_tentativas})...")
            
            agora = datetime.now().isoformat()
            
            # Buscar vendas expiradas (com limite para evitar sobrecarga)
            resultado = supabase.table("vendas")\
                .select("id")\
                .lt("expira_em", agora)\
                .limit(50)\
                .execute()
            
            if not resultado.data:
                print(f"✅ [{datetime.now().strftime('%H:%M:%S')}] Nenhuma venda expirada encontrada")
                return True
            
            # Deletar vendas encontradas
            ids_deletados = []
            ids_com_erro = []
            
            for venda in resultado.data:
                try:
                    supabase.table("vendas")\
                        .delete()\
                        .eq("id", venda["id"])\
                        .execute()
                    ids_deletados.append(venda["id"])
                except Exception as e:
                    ids_com_erro.append((venda["id"], str(e)))
                    print(f"⚠️ Erro ao deletar venda {venda['id']}: {e}")
            
            # Log do resultado
            if ids_deletados:
                print(f"✅ [{datetime.now().strftime('%H:%M:%S')}] {len(ids_deletados)} vendas expiradas deletadas")
            
            if ids_com_erro:
                print(f"⚠️ [{datetime.now().strftime('%H:%M:%S')}] {len(ids_com_erro)} vendas com erro ao deletar")
            
            return True
            
        except httpx.RemoteProtocolError as e:
            print(f"🔌 [{datetime.now().strftime('%H:%M:%S')}] Erro de protocolo HTTP (tentativa {tentativa + 1}/{max_tentativas}): {e}")
            
            if tentativa < max_tentativas - 1:
                tempo_espera = backoff_inicial * (2 ** tentativa)  # Backoff exponencial
                print(f"⏳ Aguardando {tempo_espera}s antes de tentar novamente...")
                time.sleep(tempo_espera)
            else:
                print(f"🔴 ERRO CRÍTICO: Falha após {max_tentativas} tentativas")
                return False
                
        except Exception as e:
            print(f"❌ [{datetime.now().strftime('%H:%M:%S')}] Erro inesperado (tentativa {tentativa + 1}/{max_tentativas}): {type(e).__name__}: {e}")
            
            if tentativa < max_tentativas - 1:
                tempo_espera = backoff_inicial * (2 ** tentativa)
                print(f"⏳ Aguardando {tempo_espera}s antes de tentar novamente...")
                time.sleep(tempo_espera)
            else:
                print(f"🔴 ERRO CRÍTICO: Não foi possível verificar vendas expiradas")
                return False
    
    return False


def gerar_qr_code(dados):
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(dados)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    return base64.b64encode(buffer.getvalue()).decode()

     
# ========== GEOLOCALIZAÇÃO DO CLIENTE ==========
    @reactive.Effect
    @reactive.event(input.geolocalizacao_cliente)
    def _salvar_geolocalizacao():
        """Salva coordenadas GPS do cliente"""
        try:
            user = user_data()
            if not user or not supabase:
                return
            
            geo = input.geolocalizacao_cliente()
            if not geo:
                return
            
            lat = geo['lat']
            lon = geo['lon']
            accuracy = geo.get('accuracy', 0)
            
            print(f"\n{'='*60}")
            print(f"📍 GEOLOCALIZAÇÃO RECEBIDA")
            print(f"{'='*60}")
            print(f"Usuário: {user.get('nome')}")
            print(f"Coordenadas: {lat}, {lon}")
            print(f"Precisão: {accuracy} metros")
            print(f"{'='*60}\n")
            
            # Atualiza no banco
            supabase.table('clientes').update({
                'latitude': lat,
                'longitude': lon,
                'usa_geolocalizacao': True
            }).eq('usuario_id', user['id']).execute()
            
            ui.notification_show(
                f"✅ Localização ativa!\n"
                f"Mostrando procedimentos próximos a você.",
                type="message",
                duration=5
            )
            
        except Exception as e:
            print(f"❌ Erro ao salvar geolocalização: {e}")
            import traceback
            traceback.print_exc()


    @reactive.Effect
    @reactive.event(input.geolocalizacao_negada)
    def _geolocalizacao_negada():
        """Quando usuário nega geolocalização"""
        try:
            print("⚠️ Usuário negou geolocalização - usando busca por cidade")
            
            ui.notification_show(
                "ℹ️ Sem problema!\n"
                "Buscaremos procedimentos na sua cidade.",
                type="info",
                duration=4
            )
            
        except Exception as e:
            print(f"❌ Erro: {e}")


    @reactive.Effect
    @reactive.event(input.usar_busca_cidade)
    def _usar_busca_cidade():
        """Quando usuário escolhe buscar por cidade"""
        try:
            print("🏙️ Usuário optou por busca por cidade")
            
            ui.notification_show(
                "🏙️ Buscaremos procedimentos na sua cidade cadastrada.",
                type="info",
                duration=4
            )
            
        except Exception as e:
            print(f"❌ Erro: {e}")

    # ========== NOVA FUNÇÃO: GERAR QR CODE PIX ==========
def gerar_pix_payload(chave, valor, beneficiario, cidade="Vitoria", txid=None):
        """
        Gera payload PIX EMV (copia e cola) corretamente com todos os campos necessários
        """
        try:
            # Função auxiliar para formatar campos EMV
            def emv_field(id, value):
                value_str = str(value)
                return f"{id}{len(value_str):02d}{value_str}"
            
            # 1. Payload Format Indicator
            payload = emv_field("00", "01")
            
            # 2. Merchant Account Information (ID 26)
            # GUI do PIX
            merchant_account = emv_field("00", "BR.GOV.BCB.PIX")
            # Chave PIX
            merchant_account += emv_field("01", str(chave))
            payload += emv_field("26", merchant_account)
            
            # 3. Merchant Category Code
            payload += emv_field("52", "0000")
            
            # 4. Transaction Currency (986 = BRL)
            payload += emv_field("53", "986")
            
            # 5. Transaction Amount (formato: 123.45)
            valor_formatado = f"{float(valor):.2f}"
            payload += emv_field("54", valor_formatado)
            
            # 6. Country Code
            payload += emv_field("58", "BR")
            
            # 7. Merchant Name (máximo 25 caracteres)
            beneficiario_limpo = str(beneficiario)[:25]
            payload += emv_field("59", beneficiario_limpo)
            
            # 8. Merchant City (máximo 15 caracteres)
            cidade_limpa = str(cidade)[:15]
            payload += emv_field("60", cidade_limpa)
            
            # 9. Additional Data Field Template (ID 62) - IMPORTANTE!
            # Este campo é exigido por muitos bancos
            additional_data = ""
            
            # Transaction ID (txid)
            if txid:
                additional_data += emv_field("05", str(txid)[:25])
            else:
                # Gera um txid baseado em timestamp
                import time
                txid_gerado = f"MEDPIX{int(time.time())}"[:25]
                additional_data += emv_field("05", txid_gerado)
            
            # Adiciona o campo 62 completo
            if additional_data:
                payload += emv_field("62", additional_data)
            
            # 10. CRC16 placeholder
            payload += "6304"
            
            # Calcula CRC16-CCITT (XModem)
            def calcular_crc16(data):
                crc = 0xFFFF
                for byte in data.encode('utf-8'):
                    crc ^= (byte << 8)
                    for _ in range(8):
                        if crc & 0x8000:
                            crc = (crc << 1) ^ 0x1021
                        else:
                            crc = crc << 1
                        crc &= 0xFFFF
                return crc
            
            crc = calcular_crc16(payload)
            payload += f"{crc:04X}"
            
            print(f"\n{'='*60}")
            print("🔍 DEBUG PIX PAYLOAD GERADO:")
            print(f"Chave: {chave}")
            print(f"Valor: R$ {valor_formatado}")
            print(f"Beneficiário: {beneficiario_limpo}")
            print(f"Cidade: {cidade_limpa}")
            print(f"Tamanho payload: {len(payload)} caracteres")
            print(f"Payload: {payload}")
            print(f"{'='*60}\n")
            
            return payload
            
        except Exception as e:
            print(f"❌ Erro ao gerar payload PIX: {e}")
            import traceback
            traceback.print_exc()
            # Retorna payload da empresa como fallback
            return PIX_COPIA_E_COLA_EMPRESA


def gerar_imagem_venda(venda_data, cliente_data, clinica_data, itens):
    """Gera imagem PNG com os dados da venda"""
    from PIL import Image, ImageDraw, ImageFont
    
    # Dimensões da imagem
    width = 800
    # Ajustamos a altura, pois teremos menos colunas
    height = 550 + (len(itens) * 30)
    
    # Cria imagem branca
    img = Image.new('RGB', (width, height), color='white')
    draw = ImageDraw.Draw(img)
    
    # Cores
    cor_primary = '#1DD1A1'
    cor_secondary = '#0D9488'
    cor_text = '#2D3748'
    cor_gray = '#546E7A'
    
    # Fontes (usando fontes padrão do sistema)
    try:
        font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 32)
        font_subtitle = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
        font_label = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16)
        font_text = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
    except:
        # Se não encontrar, usa fonte padrão
        font_title = ImageFont.load_default()
        font_subtitle = ImageFont.load_default()
        font_label = ImageFont.load_default()
        font_text = ImageFont.load_default()
        font_small = ImageFont.load_default()
    
    y = 30
    
    # ========== CABEÇALHO ==========
    # Fundo do cabeçalho
    draw.rectangle([(0, 0), (width, 100)], fill=cor_primary)
    
    # Título
    draw.text((40, 25), "MedPIX", fill='white', font=font_title)
    # O código da venda (VND...) já aparece aqui, como solicitado.
    draw.text((40, 65), f"Venda #{venda_data.get('numero_venda', 'N/A')}", 
              fill='white', font=font_subtitle)
    
    y = 130
    
    # ========== DADOS DA CLÍNICA ==========
    draw.text((40, y), "CLÍNICA:", fill=cor_primary, font=font_label)
    y += 25
    draw.text((40, y), clinica_data.get('razao_social', 'N/A'), fill=cor_text, font=font_text)
    y += 20
    draw.text((40, y), f"CNPJ: {formatar_cnpj(clinica_data.get('cnpj', ''))}", 
              fill=cor_gray, font=font_small)
    
    y += 40
    
    # ========== DADOS DO CLIENTE ==========
    draw.text((40, y), "CLIENTE:", fill=cor_primary, font=font_label)
    y += 25
    draw.text((40, y), cliente_data.get('nome_completo', 'N/A'), fill=cor_text, font=font_text)
    y += 20
    draw.text((40, y), f"CPF: {formatar_cpf(cliente_data.get('cpf', ''))}", 
              fill=cor_gray, font=font_small)
    
    y += 40
    
    # ========== LINHA SEPARADORA ==========
    draw.line([(40, y), (width-40, y)], fill='#e2e8f0', width=2)
    y += 30
    
    # ========== PROCEDIMENTOS ==========
    draw.text((40, y), "PROCEDIMENTOS:", fill=cor_primary, font=font_label)
    y += 30
    
    # Cabeçalho da tabela (sem os valores)
    draw.text((40, y), "Procedimento", fill=cor_gray, font=font_small)
    draw.text((660, y), "Quantidade", fill=cor_gray, font=font_small) # Posição ajustada
    # draw.text((520, y), "Preço Unit.", fill=cor_gray, font=font_small) # <-- REMOVIDO
    # draw.text((660, y), "Subtotal", fill=cor_gray, font=font_small)    # <-- REMOVIDO
    y += 20
    draw.line([(40, y), (width-40, y)], fill='#e2e8f0', width=1)
    y += 10
    
    # Itens (sem os valores)
    for item in itens:
        nome = item.get('nome', 'N/A')
        # Aumentamos o limite do nome do procedimento, pois há mais espaço
        if len(nome) > 50:
            nome = nome[:47] + "..."
        
        qtd = item.get('quantidade', 1)
        
        draw.text((40, y), nome, fill=cor_text, font=font_text)
        draw.text((660, y), str(qtd), fill=cor_text, font=font_text) # Posição ajustada
        # draw.text((520, y), formatar_moeda(preco), fill=cor_text, font=font_text)    # <-- REMOVIDO
        # draw.text((660, y), formatar_moeda(subtotal), fill=cor_text, font=font_text) # <-- REMOVIDO
        y += 25
    
    y += 10
    draw.line([(40, y), (width-40, y)], fill='#e2e8f0', width=2)
    y += 20
    
   
    y += 60 # Mantemos o espaçamento
    
    # ========== QR CODE (se existir) ==========
    if venda_data.get('qr_code'):
        try:
            qr_data = base64.b64decode(venda_data['qr_code'])
            qr_img = Image.open(BytesIO(qr_data))
            qr_img = qr_img.resize((120, 120))
            img.paste(qr_img, (40, y))
        except:
            pass
    
    # ========== RODAPÉ ==========
    y_footer = height - 40
    draw.text((40, y_footer), f"Gerado em: {datetime.now().strftime('%d/%m/%Y às %H:%M')}", 
              fill=cor_gray, font=font_small)
    draw.text((width-200, y_footer), "www.medpix.app.br", 
              fill=cor_gray, font=font_small)
    
    # Converte para bytes
    buffer = BytesIO()
    img.save(buffer, format='PNG', quality=95)
    buffer.seek(0)
    
    return buffer.getvalue()

def gerar_imagem_compartilhavel(venda_data, cliente_data, clinica_data, itens):
    """Gera imagem PNG para compartilhar com beneficiário"""
    try:
        print("🖼️ [IMG-GEN] Iniciando geração da imagem compartilhável...")
        tipo_compra = venda_data.get('tipo_compra', 'proprio')
        
        # Define o título e a mensagem inicial
        if tipo_compra == 'presente':
            titulo_principal = "🎁 Você Ganhou um Presente! 🎁"
            beneficiario_nome = venda_data.get('beneficiario_nome', 'Beneficiário')
            comprador_nome = cliente_data.get('nome_completo', 'Alguém especial')
            mensagem_inicial = f"Olá, {beneficiario_nome.split()[0]}! {comprador_nome.split()[0]} te deu um presente para cuidar da saúde!"
            mostrar_pix = False
            cor_header = (22, 163, 74) # Verde Escuro
        else: # "para_outra_pessoa"
            titulo_principal = "✨ Detalhes para seu Atendimento ✨"
            beneficiario_nome = venda_data.get('beneficiario_nome', 'Beneficiário')
            mensagem_inicial = f"Olá, {beneficiario_nome.split()[0]}! Seguem os detalhes para seu atendimento e pagamento."
            mostrar_pix = True
            cor_header = (59, 130, 246) # Azul
            
        # --- Configurações da Imagem ---
        width = 800
        padding = 40
        cor_fundo = (255, 255, 255)
        cor_texto_principal = (30, 41, 59)
        cor_texto_secundario = (71, 85, 105)
        cor_destaque = cor_header
        
        # --- CORREÇÃO: Carrega fontes locais da pasta /fonts ---
        try:
            print("🖼️ [IMG-GEN] Carregando fontes locais...")
            font_path = "fonts/Roboto-Regular.ttf"
            font_bold_path = "fonts/Roboto-Bold.ttf"
            font_title = ImageFont.truetype(font_bold_path, 32)
            font_h2 = ImageFont.truetype(font_bold_path, 24)
            font_h3 = ImageFont.truetype(font_bold_path, 18)
            font_text = ImageFont.truetype(font_path, 16)
            font_small = ImageFont.truetype(font_path, 14)
            font_mono = ImageFont.truetype(font_bold_path, 16) # Usar bold para o PIX
            print("🖼️ [IMG-GEN] Fontes carregadas com sucesso.")
        except IOError as e:
            print(f"❌ ERRO FATAL: Não foi possível carregar as fontes da pasta /fonts. {e}")
            print("❌ Verifique se os arquivos 'Roboto-Regular.ttf' e 'Roboto-Bold.ttf' existem na pasta 'fonts'.")
            # Retorna uma imagem de erro
            img = Image.new('RGB', (400, 100), (255, 255, 255))
            draw = ImageDraw.Draw(img)
            draw.text((10, 10), "Erro: Fontes não encontradas.", fill=(255,0,0))
            draw.text((10, 40), "Verifique a pasta /fonts no servidor.", fill=(0,0,0))
            buffer = BytesIO()
            img.save(buffer, format='PNG')
            buffer.seek(0)
            return buffer.getvalue()
        # --- FIM DA CORREÇÃO DE FONTES ---

        # --- Calcula Altura Dinâmica ---
        y = 0
        y += 80 # Header
        y += 40 # Padding
        linhas_msg = textwrap.wrap(mensagem_inicial, width=70)
        y += len(linhas_msg) * 25
        
        y += 60 # Seção Atendimento
        y += 2 * 30 # 2 linhas
        
        y += 60 # Seção Clínica
        y += 2 * 30 # 2 linhas
        
        y += 60 # Seção Detalhes
        y += 30 # Código
        y += 30 # Procedimentos (título)
        y += len(itens) * 30 # Linhas de itens
        
        qr_height = 0
        if mostrar_pix:
            y += 60 # Seção PIX
            y += 30 # Título
            y += 30 # Chave
            y += 200 # Espaço para QR Code
            qr_height = 180
            
        y += 80 # Seção Prazo (aumentado para caber o box)
        y += 50 # Footer
        
        height = y
        
        # --- Cria Imagem e Desenha ---
        img = Image.new('RGB', (width, height), cor_fundo)
        draw = ImageDraw.Draw(img)
        
        y = 0
        
        # 1. Header
        draw.rectangle([(0, 0), (width, 80)], fill=cor_destaque)
        draw.text((padding, 24), titulo_principal, fill=(255, 255, 255), font=font_title)
        y = 80 + padding
        
        # 2. Mensagem Inicial
        for i, line in enumerate(linhas_msg):
            draw.text((padding, y + (i * 25)), line, fill=cor_texto_secundario, font=font_text)
        y += len(linhas_msg) * 25 + padding
        
        # 3. Seção Atendimento
        draw.line([(padding, y-10), (width-padding, y-10)], fill=(226, 232, 240), width=2)
        draw.text((padding, y), "👤 Para Atendimento", fill=cor_destaque, font=font_h2)
        y += 40
        draw.text((padding, y), f"Nome: {beneficiario_nome}", fill=cor_texto_principal, font=font_h3)
        y += 30
        draw.text((padding, y), f"CPF: {formatar_cpf(venda_data.get('beneficiario_cpf', 'N/I'))}", fill=cor_texto_principal, font=font_h3)
        y += padding
        
        # 4. Seção Clínica
        draw.line([(padding, y-10), (width-padding, y-10)], fill=(226, 232, 240), width=2)
        draw.text((padding, y), "🏥 Clínica", fill=cor_destaque, font=font_h2)
        y += 40
        clinica_nome = clinica_data.get('nome_fantasia') or clinica_data.get('razao_social', 'N/A')
        draw.text((padding, y), f"Nome: {clinica_nome}", fill=cor_texto_principal, font=font_text)
        y += 30
        endereco = f"{clinica_data.get('endereco_rua', '')}, {clinica_data.get('endereco_cidade', '')}/{clinica_data.get('endereco_estado', '')}"
        draw.text((padding, y), f"Endereço: {endereco}", fill=cor_texto_principal, font=font_text)
        y += padding

        # 5. Seção Detalhes
        draw.line([(padding, y-10), (width-padding, y-10)], fill=(226, 232, 240), width=2)
        draw.text((padding, y), "🔬 Detalhes da Compra", fill=cor_destaque, font=font_h2)
        y += 40
        draw.rectangle([(padding, y), (width-padding, y+40)], fill=(241, 245, 249))
        draw.text((padding + 15, y + 10), f"Código de Atendimento: {venda_data.get('numero_venda', 'N/A')}", fill=cor_texto_principal, font=font_h3)
        y += 60
        draw.text((padding, y), "Procedimentos:", fill=cor_texto_secundario, font=font_text)
        y += 30
        for item in itens:
            nome = item.get('nome_procedimento', item.get('nome', 'N/A'))
            draw.text((padding + 20, y), f"• {nome} (Qtd: {item.get('quantidade', 1)})", fill=cor_texto_principal, font=font_text)
            y += 30
        y += padding
        
        # 6. Seção PIX (COM QRCODE REAL)
        if mostrar_pix:
            print("🖼️ [IMG-GEN] ... Gerando QR Code PIX ...")
            draw.line([(padding, y-10), (width-padding, y-10)], fill=(226, 232, 240), width=2)
            draw.text((padding, y), "💰 Informações para Pagamento", fill=cor_destaque, font=font_h2)
            y += 40
            
            chave_pix_cnpj = "59.170.478/0001-02"
            valor_total = venda_data.get('valor_total', 0)
            
            # Gera payload PIX (usando sua função existente)
            payload = gerar_pix_payload(
                chave="59170478000102",
                valor=valor_total,
                beneficiario="MedPIX",
                cidade="SAO PAULO"
            )
            
            # Gera QR Code
            try:
                qr_img = qrcode.make(payload)
                qr_img = qr_img.resize((qr_height, qr_height))
                img.paste(qr_img, (width - padding - qr_height, y))
                print("🖼️ [IMG-GEN] QR Code gerado e colado na imagem.")
            except Exception as e:
                print(f"❌ Erro ao gerar QR Code: {e}")
                draw.rectangle([(width - padding - qr_height, y), (width - padding, y + qr_height)], fill=(200, 200, 200))
                draw.text((width - padding - qr_height + 10, y + 80), "Erro QR", fill=(0,0,0), font=font_small)

            draw.text((padding, y), f"Chave PIX (CNPJ):", fill=cor_texto_secundario, font=font_text)
            y += 30
            draw.text((padding, y), f"{chave_pix_cnpj}", fill=cor_texto_principal, font=font_h3)
            y += 40
            draw.text((padding, y), f"Valor Total: {formatar_moeda(valor_total)}", fill=cor_texto_principal, font=font_h3)
            y += 40
            draw.text((padding, y), f"Escaneie o QR Code ao lado", fill=cor_texto_secundario, font=font_text)
            y += 40
            draw.text((padding, y), f"ou use o 'Copia e Cola' enviado no WhatsApp.", fill=cor_texto_secundario, font=font_small)
            y += padding + 20
        
        # 7. Seção Prazo
        draw.rectangle([(padding, y), (width-padding, y+60)], fill=(254, 226, 226))
        draw.text((padding + 20, y + 20), "⚠️ PRAZO: Você tem 30 dias para agendar junto à clínica!", fill=(185, 28, 28), font=font_h3)
        y += 80
        
        # 8. Footer
        draw.text((width - padding - 150, y), "Gerado por MedPIX", fill=cor_texto_secundario, font=font_small)

        # Converte para bytes
        buffer = BytesIO()
        img.save(buffer, format='PNG', quality=95)
        buffer.seek(0)
        
        print(f"✅ [IMG-GEN] Imagem gerada com sucesso! Tamanho: {len(buffer.getvalue())} bytes")
        
        return buffer.getvalue()
        
    except Exception as e:
        print(f"❌ Erro ao gerar imagem compartilhável: {e}")
        import traceback
        traceback.print_exc()
        # Retorna uma imagem de erro
        img = Image.new('RGB', (400, 200), (255, 255, 255))
        draw = ImageDraw.Draw(img)
        draw.text((20, 20), "Erro ao gerar imagem", fill=(255, 0, 0))
        draw.text((20, 50), str(e), fill=(0, 0, 0))
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        return buffer.getvalue()


def gerar_contrato_parceria(clinica_data, usuario, senha, vendedor_nome):
    """Versão de teste simplificada"""
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4
        
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4
        
        # PDF super simples
        c.setFont("Helvetica-Bold", 20)
        c.drawString(100, height - 100, "CONTRATO DE PARCERIA")
        
        c.setFont("Helvetica", 12)
        c.drawString(100, height - 150, "Clinica: " + str(clinica_data.get('razao_social', 'N/A')))
        c.drawString(100, height - 180, "CNPJ: " + str(usuario))
        c.drawString(100, height - 210, "Senha: " + str(senha))
        c.drawString(100, height - 240, "Vendedor: " + str(vendedor_nome))
        
        c.showPage()
        c.save()
        
        buffer.seek(0)
        pdf_bytes = buffer.getvalue()
        
        print(f"✅ PDF gerado com sucesso! Tamanho: {len(pdf_bytes)} bytes")
        
        return pdf_bytes
        
    except Exception as e:
        print(f"❌ ERRO na geracao do PDF: {e}")
        import traceback
        traceback.print_exc()
        raise

# ==================== CONFIGURAÇÕES DE NOTIFICAÇÃO ====================

# Configurações Resend (não precisa mais de SMTP)
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
EMAIL_FROM = os.environ.get("EMAIL_FROM", "noreply@medpix.app.br")

# Mantido para compatibilidade (não usado mais)
EMAIL_HOST = ""
EMAIL_PORT = 0
EMAIL_USER = ""
EMAIL_PASSWORD = ""

WHATSAPP_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "")
WHATSAPP_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "")
WHATSAPP_FROM = os.environ.get("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")

# ==================== FUNÇÕES DE NOTIFICAÇÃO ====================

def enviar_email(destinatario, assunto, corpo_html, corpo_texto=""):
    """
    Envia email via Resend API
    
    Args:
        destinatario: Email do destinatário
        assunto: Assunto do email
        corpo_html: Corpo do email em HTML
        corpo_texto: Versão texto alternativa (opcional)
    
    Returns:
        bool: True se enviado com sucesso
    """
    try:
        RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
        
        if not RESEND_API_KEY:
            print("⚠️ Resend API Key não configurada")
            return False
        
        print(f"🔍 Enviando email via Resend para: {destinatario}")
        print(f"🔍 Assunto: {assunto}")
        print(f"🔍 From: {EMAIL_FROM}")
        
        url = "https://api.resend.com/emails"
        
        headers = {
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type": "application/json"
        }
        
        # Monta o payload
        data = {
            "from": f"MedPIX <{EMAIL_FROM}>",
            "to": [destinatario],
            "subject": assunto,
            "html": corpo_html
        }
        
        # Adiciona versão texto se fornecida
        if corpo_texto:
            data["text"] = corpo_texto
        
        print(f"🔍 Chamando API Resend...")
        response = requests.post(url, headers=headers, json=data)
        
        print(f"🔍 Status Code: {response.status_code}")
        
        if response.status_code == 200:
            response_data = response.json()
            email_id = response_data.get('id', 'unknown')
            print(f"✅ Email enviado com sucesso para {destinatario}")
            print(f"✅ ID do email: {email_id}")
            return True
        else:
            print(f"❌ Erro ao enviar email: {response.status_code}")
            print(f"❌ Resposta: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Erro ao enviar email via Resend: {e}")
        import traceback
        traceback.print_exc()
        return False

def enviar_email_boas_vindas_cliente(nome, email, codigo_cliente):
    """
    Envia email de boas-vindas para novo cliente
    
    Args:
        nome: Nome do cliente
        email: Email do cliente
        codigo_cliente: Código do cliente
    
    Returns:
        bool: True se enviado com sucesso
    """
    try:
        primeiro_nome = nome.split()[0]
        
        assunto = "🎉 Bem-vindo ao MedPIX!"
        
        corpo_html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; font-family: Arial, sans-serif; background-color: #f3f4f6;">
    <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #f3f4f6; padding: 20px;">
        <tr>
            <td align="center">
                <table width="600" cellpadding="0" cellspacing="0" style="background-color: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);">
                    
                    <!-- Header -->
                    <tr>
                        <td style="background: linear-gradient(135deg, #1DD1A1 0%, #0D9488 100%); padding: 30px; text-align: center;">
                            <h1 style="margin: 0; color: #ffffff; font-size: 28px;">🎉 Bem-vindo ao MedPIX!</h1>
                        </td>
                    </tr>
                    
                    <!-- Saudação -->
                    <tr>
                        <td style="padding: 30px 30px 20px 30px;">
                            <h2 style="margin: 0 0 15px 0; color: #2D3748; font-size: 22px;">Olá, {primeiro_nome}! 👋</h2>
                            <p style="margin: 0; color: #475569; font-size: 16px; line-height: 1.6;">
                                Seu cadastro foi concluído com sucesso! Agora você faz parte da maior plataforma de economia em procedimentos médicos.
                            </p>
                        </td>
                    </tr>
                    
                    <!-- Seu Código -->
                    <tr>
                        <td style="padding: 0 30px 20px 30px;">
                            <div style="background: #f1f5f9; padding: 15px; border-radius: 8px; text-align: center; border-left: 4px solid #1DD1A1;">
                                <p style="margin: 0 0 5px 0; color: #546E7A; font-size: 14px;">Seu código de cliente:</p>
                                <p style="margin: 0; color: #1DD1A1; font-size: 24px; font-weight: bold; font-family: monospace;">{codigo_cliente}</p>
                            </div>
                        </td>
                    </tr>
                    
                    <!-- Como Funciona -->
                    <tr>
                        <td style="padding: 0 30px 20px 30px;">
                            <h3 style="margin: 0 0 15px 0; color: #2D3748; font-size: 18px;">📋 Como fazer sua primeira compra:</h3>
                            <ol style="margin: 0; padding-left: 20px; color: #475569; font-size: 15px; line-height: 1.8;">
                                <li><strong>Busque</strong> o procedimento que precisa</li>
                                <li><strong>Adicione</strong> ao carrinho</li>
                                <li><strong>Pague</strong> e receba cashback!</li>
                            </ol>
                        </td>
                    </tr>
                    
                    <!-- Cashback -->
                    <tr>
                        <td style="padding: 0 30px 20px 30px;">
                            <div style="background: linear-gradient(135deg, #10b981, #059669); padding: 20px; border-radius: 8px;">
                                <h3 style="margin: 0 0 10px 0; color: #ffffff; font-size: 18px;">💰 Níveis de Cashback</h3>
                                <table width="100%" cellpadding="5" cellspacing="0">
                                    <tr>
                                        <td style="color: #ffffff; font-size: 14px;">🥉 Bronze (0-5 compras):</td>
                                        <td style="color: #ffffff; font-size: 14px; text-align: right;"><strong>3%</strong></td>
                                    </tr>
                                    <tr>
                                        <td style="color: #ffffff; font-size: 14px;">🥈 Prata (6-15 compras):</td>
                                        <td style="color: #ffffff; font-size: 14px; text-align: right;"><strong>5%</strong></td>
                                    </tr>
                                    <tr>
                                        <td style="color: #ffffff; font-size: 14px;">🥇 Ouro (16+ compras):</td>
                                        <td style="color: #ffffff; font-size: 14px; text-align: right;"><strong>7%</strong></td>
                                    </tr>
                                </table>
                            </div>
                        </td>
                    </tr>
                    
                    <!-- Indique e Ganhe -->
                    <tr>
                        <td style="padding: 0 30px 30px 30px;">
                            <div style="background: #fef3c7; padding: 20px; border-radius: 8px; border: 2px solid #f59e0b;">
                                <h3 style="margin: 0 0 10px 0; color: #92400e; font-size: 18px;">🎁 Indique e Ganhe Mais!</h3>
                                <p style="margin: 0 0 10px 0; color: #78350f; font-size: 15px; line-height: 1.6;">
                                    <strong>Compartilhe com amigos e familiares!</strong>
                                </p>
                                <p style="margin: 0; color: #78350f; font-size: 14px; line-height: 1.6;">
                                    ✨ Cada pessoa que você indicar ganha desconto na primeira compra<br>
                                    💵 Você ganha cashback extra a cada indicação bem-sucedida<br>
                                    📈 Quanto mais indica, mais ganha!
                                </p>
                            </div>
                        </td>
                    </tr>
                    
                    <!-- CTA -->
                    <tr>
                        <td style="padding: 0 30px 30px 30px; text-align: center;">
                            <a href="https://app.medpix.app.br" style="display: inline-block; background: linear-gradient(135deg, #1DD1A1, #0D9488); color: #ffffff; text-decoration: none; padding: 15px 40px; border-radius: 8px; font-size: 16px; font-weight: bold;">
                                🚀 Acessar MedPIX
                            </a>
                        </td>
                    </tr>
                    
                    <!-- Footer -->
                    <tr>
                        <td style="background-color: #f8fafc; padding: 20px 30px; text-align: center; border-top: 1px solid #e2e8f0;">
                            <p style="margin: 0 0 5px 0; color: #546E7A; font-size: 13px;">
                                📧 Dúvidas? Responda este email ou entre em contato conosco
                            </p>
                            <p style="margin: 0; color: #94a3b8; font-size: 12px;">
                                MedPIX - Economize em saúde
                            </p>
                        </td>
                    </tr>
                    
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""
        
        corpo_texto = f"""
🎉 Bem-vindo ao MedPIX, {primeiro_nome}!

Seu cadastro foi concluído com sucesso!

🆔 Seu código: {codigo_cliente}

📋 Como fazer sua primeira compra:
1. Busque o procedimento que precisa
2. Adicione ao carrinho
3. Pague e receba cashback!

💰 Níveis de Cashback:
🥉 Bronze (0-5 compras): 3%
🥈 Prata (6-15 compras): 5%
🥇 Ouro (16+ compras): 7%

🎁 Indique e Ganhe!
Compartilhe com amigos e familiares. Cada indicação te dá cashback extra!

🚀 Acesse: https://app.medpix.app.br

Dúvidas? Responda este email!
"""
        
        print(f"📧 Enviando email de boas-vindas para {email}...")
        resultado = enviar_email(email, assunto, corpo_html, corpo_texto)
        
        if resultado:
            print(f"✅ Email de boas-vindas enviado com sucesso!")
        else:
            print(f"⚠️ Não foi possível enviar email de boas-vindas")
        
        return resultado
        
    except Exception as e:
        print(f"❌ Erro ao enviar email de boas-vindas: {e}")
        return False


def enviar_email_boas_vindas_clinica(razao_social, email):
    """
    Envia email de boas-vindas para nova clínica com instruções
    
    Args:
        razao_social: Nome da clínica
        email: Email da clínica
    
    Returns:
        bool: True se enviado com sucesso
    """
    try:
        assunto = "Bem-vindo ao MedPIX - Instruções de Uso"
        
        corpo_html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
</head>
<body style="margin: 0; padding: 20px; font-family: Arial, sans-serif; background-color: #f9fafb;">
    <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 8px; overflow: hidden;">
        
        <div style="background: linear-gradient(135deg, #1DD1A1, #0D9488); padding: 30px; text-align: center;">
            <h1 style="margin: 0; color: #ffffff; font-size: 24px;">Bem-vindo ao MedPIX</h1>
        </div>
        
        <div style="padding: 30px;">
            <p style="margin: 0 0 20px 0; color: #1f2937; font-size: 16px;">
                Olá, <strong>{razao_social}</strong>!
            </p>
            
            <p style="margin: 0 0 20px 0; color: #4b5563; font-size: 15px; line-height: 1.6;">
                Seu cadastro foi aprovado com sucesso. Agora você faz parte da rede MedPIX.
            </p>
            
            <div style="background-color: #fef3c7; padding: 20px; border-radius: 6px; border-left: 4px solid #f59e0b; margin: 20px 0;">
                <h3 style="margin: 0 0 15px 0; color: #92400e; font-size: 18px;">Informações Importantes</h3>
                
                <p style="margin: 0 0 10px 0; color: #78350f; font-size: 14px;">
                    <strong>💰 Comissão:</strong> 12% sobre cada venda
                </p>
                
                <p style="margin: 0 0 10px 0; color: #78350f; font-size: 14px;">
                    <strong>💳 Pagamento em 2 parcelas:</strong>
                </p>
                <ul style="margin: 5px 0 10px 20px; padding: 0; color: #78350f; font-size: 13px;">
                    <li>Parcela 1 (50%): Paga antecipadamente após confirmação</li>
                    <li>Parcela 2 (50%): Paga após finalização dos atendimentos</li>
                </ul>
                
                <p style="margin: 0; color: #78350f; font-size: 14px;">
                    <strong>📱 Controle:</strong> Atendimentos e financeiro pelo app MedPIX
                </p>
            </div>
            
            <h2 style="margin: 30px 0 15px 0; color: #1f2937; font-size: 18px;">Como usar o MedPIX</h2>
            
            <div style="margin-bottom: 20px;">
                <h3 style="margin: 0 0 10px 0; color: #1DD1A1; font-size: 16px;">1. Cadastrar Procedimentos</h3>
                <p style="margin: 0 0 10px 0; color: #4b5563; font-size: 14px; line-height: 1.6;">
                    Acesse a aba <strong>"Cadastrar Procedimento"</strong> e adicione os procedimentos que sua clínica oferece (nome, grupo, preço).
                </p>
                <p style="margin: 0; color: #6b7280; font-size: 13px; font-style: italic;">
                    💡 Você também pode importar uma planilha Excel com todos os procedimentos.
                </p>
            </div>
            
            <div style="margin-bottom: 20px;">
                <h3 style="margin: 0 0 10px 0; color: #1DD1A1; font-size: 16px;">2. Atender Clientes</h3>
                <p style="margin: 0 0 10px 0; color: #4b5563; font-size: 14px; line-height: 1.6;">
                    Quando o cliente chegar para atendimento:
                </p>
                <ul style="margin: 5px 0 0 20px; padding: 0; color: #4b5563; font-size: 14px;">
                    <li>Acesse <strong>"Atendimento ao Cliente"</strong></li>
                    <li>Digite o código da venda (ex: VND20251019XXXX)</li>
                    <li>Verifique se o cliente está apto</li>
                    <li>Marque o atendimento como concluído</li>
                </ul>
            </div>
            
            <div style="margin-bottom: 20px;">
                <h3 style="margin: 0 0 10px 0; color: #1DD1A1; font-size: 16px;">3. Controle Financeiro</h3>
                <p style="margin: 0; color: #4b5563; font-size: 14px; line-height: 1.6;">
                    Na aba <strong>"Atendimentos Realizados"</strong> você acompanha:
                </p>
                <ul style="margin: 5px 0 0 20px; padding: 0; color: #4b5563; font-size: 14px;">
                    <li>Quantidade de atendimentos</li>
                    <li>Pagamentos recebidos (Parcela 1)</li>
                    <li>Valores a receber (Parcela 2 após atendimentos)</li>
                </ul>
            </div>
            
            <div style="background-color: #dcfce7; padding: 20px; border-radius: 6px; margin: 20px 0;">
                <h3 style="margin: 0 0 10px 0; color: #15803d; font-size: 16px;">Precisa de Ajuda?</h3>
                <p style="margin: 0; color: #166534; font-size: 14px; line-height: 1.6;">
                    Entre em contato conosco respondendo este email ou através do suporte no app.
                </p>
            </div>
            
            <div style="text-align: center; margin: 30px 0;">
                <a href="https://app.medpix.app.br" style="display: inline-block; background-color: #1DD1A1; color: #ffffff; text-decoration: none; padding: 12px 30px; border-radius: 6px; font-size: 15px; font-weight: 600;">
                    Acessar MedPIX
                </a>
            </div>
        </div>
        
        <div style="background-color: #f9fafb; padding: 20px; text-align: center; border-top: 1px solid #e5e7eb;">
            <p style="margin: 0; color: #6b7280; font-size: 13px;">
                Dúvidas? Responda este email
            </p>
            <p style="margin: 5px 0 0 0; color: #9ca3af; font-size: 12px;">
                MedPIX - Plataforma de Procedimentos Médicos
            </p>
        </div>
        
    </div>
</body>
</html>
"""
        
        corpo_texto = f"""
Bem-vindo ao MedPIX

{razao_social}

Seu cadastro foi aprovado com sucesso!

INFORMAÇÕES IMPORTANTES:
- Comissão: 12% sobre cada venda
- Pagamento em 2 parcelas:
  * Parcela 1 (50%): Paga antecipadamente
  * Parcela 2 (50%): Paga após atendimentos
- Controle: Via app MedPIX

COMO USAR:

1. CADASTRAR PROCEDIMENTOS
   - Acesse "Cadastrar Procedimento"
   - Adicione nome, grupo e preço
   - Ou importe planilha Excel

2. ATENDER CLIENTES
   - Acesse "Atendimento ao Cliente"
   - Digite o código da venda
   - Verifique se está apto
   - Marque como concluído

3. CONTROLE FINANCEIRO
   - Acesse "Atendimentos Realizados"
   - Acompanhe pagamentos recebidos
   - Veja valores a receber

Acesse: https://medpix.app.br

Dúvidas? Responda este email!

--
MedPIX - Plataforma de Procedimentos Médicos
"""
        
        print(f"📧 Enviando email de boas-vindas para clínica: {email}...")
        resultado = enviar_email(email, assunto, corpo_html, corpo_texto)
        
        if resultado:
            print(f"✅ Email enviado com sucesso para {razao_social}")
        else:
            print(f"⚠️ Não foi possível enviar email para {razao_social}")
        
        return resultado
        
    except Exception as e:
        print(f"❌ Erro ao enviar email para clínica: {e}")
        return False


def enviar_whatsapp(numero, mensagem):
    """
    Envia mensagem WhatsApp via Twilio
    
    Args:
        numero: Número com código do país (ex: +5511999999999)
        mensagem: Texto da mensagem
    
    Returns:
        bool: True se enviado com sucesso
    """
    try:
        if not WHATSAPP_ACCOUNT_SID or not WHATSAPP_AUTH_TOKEN:
            print("⚠️ Credenciais do Twilio não configuradas")
            return False
        
        url = f"https://api.twilio.com/2010-04-01/Accounts/{WHATSAPP_ACCOUNT_SID}/Messages.json"
        
        if not numero.startswith('whatsapp:'):
            if not numero.startswith('+'):
                numero = f"+55{numero}"
            numero = f"whatsapp:{numero}"
        
        data = {
            'From': WHATSAPP_FROM,
            'To': numero,
            'Body': mensagem
        }
        
        response = requests.post(
            url,
            data=data,
            auth=(WHATSAPP_ACCOUNT_SID, WHATSAPP_AUTH_TOKEN)
        )
        
        if response.status_code == 201:
            print(f"✅ WhatsApp enviado para {numero}")
            return True
        else:
            print(f"❌ Erro ao enviar WhatsApp: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Erro ao enviar WhatsApp: {e}")
        return False

# ==================== FUNÇÕES DE GEOLOCALIZAÇÃO ====================

def calcular_distancia(lat1, lon1, lat2, lon2):
    """Calcula distância entre dois pontos (Haversine)"""
    from math import radians, sin, cos, sqrt, atan2
    
    if not all([lat1, lon1, lat2, lon2]):
        return None
    
    R = 6371.0
    try:
        lat1_rad = radians(float(lat1))
        lon1_rad = radians(float(lon1))
        lat2_rad = radians(float(lat2))
        lon2_rad = radians(float(lon2))
        
        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad
        
        a = sin(dlat / 2)**2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlon / 2)**2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))
        
        return round(R * c, 2)
    except:
        return None


def buscar_procedimentos_hibrido(termo_busca, cliente_lat=None, cliente_lon=None, cidade=None, estado=None, raio_km=50):
    """Busca procedimentos E PACOTES com geolocalização ou cidade"""
    try:
        print(f"\n{'='*80}")
        print(f"🔍 BUSCA HÍBRIDA (PROCEDIMENTOS E PACOTES)")
        print(f"{'='*80}")
        print(f"Termo: {termo_busca}")
        print(f"Cliente GPS: lat={cliente_lat}, lon={cliente_lon}")
        print(f"Cliente Cidade: {cidade}/{estado}")
        print(f"Raio: {raio_km} km")
        print(f"{'='*80}\n")
        
        # 1. Busca PROCEDIMENTOS
        result_procs = supabase.table('procedimentos').select(
            '*, clinicas(id, nome_fantasia, razao_social, endereco_cidade, endereco_estado, latitude, longitude, whatsapp)'
        ).ilike('nome', f'%{termo_busca}%').eq('ativo', True).execute()
        
        # 2. Busca PACOTES
        result_pacotes = supabase.table('pacotes').select(
            '*, clinicas(id, nome_fantasia, razao_social, endereco_cidade, endereco_estado, latitude, longitude, whatsapp)'
        ).ilike('nome', f'%{termo_busca}%').eq('ativo', True).execute()

        print(f"📊 Procedimentos encontrados: {len(result_procs.data if result_procs.data else [])}")
        print(f"🎁 Pacotes encontrados: {len(result_pacotes.data if result_pacotes.data else [])}")

        # 3. Adiciona tipo_item e mescla
        itens_mesclados = []
        if result_procs.data:
            for proc in result_procs.data:
                proc['tipo_item'] = 'procedimento'
                proc['preco'] = proc.get('preco') # Preço normal
                itens_mesclados.append(proc)
        
        if result_pacotes.data:
            for pacote in result_pacotes.data:
                pacote['tipo_item'] = 'pacote'
                pacote['preco'] = pacote.get('valor_final') # Preço com desconto
                
                # Busca os nomes dos sub-itens para exibir no card
                try:
                    itens_pacote_res = supabase.table('pacotes_itens').select(
                        'procedimentos(nome)'
                    ).eq('pacote_id', pacote['id']).limit(5).execute()
                    
                    if itens_pacote_res.data:
                        nomes_itens = [item['procedimentos']['nome'] for item in itens_pacote_res.data if item.get('procedimentos')]
                        pacote['nomes_sub_itens'] = nomes_itens
                    else:
                        pacote['nomes_sub_itens'] = []
                except Exception as e:
                    print(f"Erro ao buscar sub-itens do pacote {pacote['id']}: {e}")
                    pacote['nomes_sub_itens'] = []
                
                itens_mesclados.append(pacote)

        if not itens_mesclados:
            print("❌ Nenhum item (procedimento ou pacote) encontrado!")
            return []
        
        print(f"📦 Total de itens mesclados: {len(itens_mesclados)}")

        itens_processados = []
        
        # ========== BUSCA POR GPS ==========
        if cliente_lat and cliente_lon:
            print(f"\n🛰️ MODO GPS ATIVADO")
            # ... (mais prints) ...
            
            clinicas_sem_gps = 0
            clinicas_fora_raio = 0
            clinicas_dentro_raio = 0
            
            # Itera sobre 'itens_mesclados'
            for item in itens_mesclados:
                clinica = item.get('clinicas')
                if not clinica:
                    print(f"⚠️ Item {item.get('nome')} ({item.get('tipo_item')}) sem clínica vinculada")
                    continue
                
                clinica_nome = clinica.get('nome_fantasia') or clinica.get('razao_social')
                clinica_lat = clinica.get('latitude')
                clinica_lon = clinica.get('longitude')
                
                if not clinica_lat or not clinica_lon:
                    clinicas_sem_gps += 1
                    print(f"⚠️ Clínica {clinica_nome} SEM coordenadas GPS cadastradas")
                    continue
                
                distancia = calcular_distancia(cliente_lat, cliente_lon, clinica_lat, clinica_lon)

                print(f"📍 {clinica_nome} ({item.get('nome')}): {distancia:.2f} km")

                if distancia is not None and distancia <= raio_km:
                    clinicas_dentro_raio += 1
                    item['distancia_km'] = round(distancia, 2)
                    item['modo_busca'] = 'gps'
                    itens_processados.append(item)
                    print(f"   ✅ DENTRO do raio ({distancia:.2f} km <= {raio_km} km)")
                else:
                    clinicas_fora_raio += 1
                    if distancia is not None:
                        print(f"   ❌ FORA do raio ({distancia:.2f} km > {raio_km} km)")
                    else:
                        print(f"   ❌ Erro ao calcular distância")
            
            # ... (Resumo GPS) ...
            
            if itens_processados:
                itens_processados.sort(key=lambda x: (x.get('distancia_km', 999), -float(x.get('preco', 0)))) # Ordena por distância, depois preço
                print(f"\n✅ Retornando {len(itens_processados)} resultados ordenados por distância")
                return itens_processados
            
            # ... (Lógica de expandir raio) ...
            if raio_km < 100:
                novo_raio = raio_km * 2
                print(f"\n⚠️ Nenhum resultado em {raio_km}km. Expandindo para {novo_raio}km...")
                return buscar_procedimentos_hibrido(termo_busca, cliente_lat, cliente_lon, cidade, estado, novo_raio)
            
            print(f"\n⚠️ Nenhum resultado até {raio_km}km. Tentando busca por cidade...")
        
        # ========== BUSCA POR CIDADE ==========
        if cidade and estado:
            print(f"\n🏙️ MODO CIDADE ATIVADO")
            # ... (prints) ...
            
            mesma_cidade = []
            mesmo_estado = []
            
            # Itera sobre 'itens_mesclados'
            for item in itens_mesclados:
                clinica = item.get('clinicas')
                if not clinica:
                    continue
                
                # ... (resto da lógica de cidade idêntica) ...
                clinica_nome = clinica.get('nome_fantasia') or clinica.get('razao_social')
                clinica_cidade = clinica.get('endereco_cidade', '').strip()
                clinica_estado = clinica.get('endereco_estado', '').strip()
                
                print(f"📍 {clinica_nome} ({item.get('nome')}): {clinica_cidade}/{clinica_estado}")
                
                if clinica_cidade.lower() == cidade.lower() and clinica_estado.upper() == estado.upper():
                    item['prioridade'] = 1
                    item['modo_busca'] = 'cidade'
                    mesma_cidade.append(item)
                    print(f"   ✅ MESMA CIDADE")
                elif clinica_estado.upper() == estado.upper():
                    item['prioridade'] = 2
                    item['modo_busca'] = 'cidade'
                    mesmo_estado.append(item)
                    print(f"   ⚠️ Mesmo estado")
                else:
                    print(f"   ❌ Outro estado")
            
            # ... (Resumo cidade) ...
            
            itens_processados = mesma_cidade + mesmo_estado
            
            if itens_processados:
                itens_processados.sort(key=lambda x: (x.get('prioridade', 999), -float(x.get('preco', 0)))) # Ordena por prioridade, depois preço
                print(f"\n✅ Retornando {len(itens_processados)} resultados")
                return itens_processados
            
            print(f"\n⚠️ Nenhum resultado em {cidade}/{estado}")
        
        # ========== SEM FILTRO (FALLBACK) ==========
        print(f"\n📋 MODO GERAL (sem filtro)")
        print(f"Retornando todos os {len(itens_mesclados)} itens\n")
        
        for item in itens_mesclados:
            item['modo_busca'] = 'geral'
            itens_processados.append(item)
        
        return itens_processados
        
    except Exception as e:
        print(f"\n❌ ERRO na busca híbrida: {e}")
        import traceback
        traceback.print_exc()
        return []


def template_email_base(titulo, conteudo, cor="#1DD1A1"):
    """Template HTML base para emails"""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="margin: 0; padding: 0; font-family: Arial, sans-serif; background-color: #f3f4f6;">
        <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #f3f4f6; padding: 20px;">
            <tr>
                <td align="center">
                    <table width="600" cellpadding="0" cellspacing="0" style="background-color: white; border-radius: 10px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                        <tr>
                            <td style="background: linear-gradient(135deg, {cor}, #0D9488); padding: 30px; text-align: center;">
                                <h1 style="color: white; margin: 0; font-size: 32px;">MedPIX</h1>
                                <p style="color: white; margin: 10px 0 0 0; opacity: 0.9;">{titulo}</p>
                            </td>
                        </tr>
                        <tr>
                            <td style="padding: 40px;">
                                {conteudo}
                            </td>
                        </tr>
                        <tr>
                            <td style="background-color: #f9fafb; padding: 20px; text-align: center; border-top: 1px solid #e5e7eb;">
                                <p style="margin: 0; color: #6b7280; font-size: 14px;">
                                    © 2025 MedPIX® - Marca registrada no INPI - Todos os direitos reservados<br>
                                    <a href="https://medpix.app.br" style="color: {cor};">www.medpix.app.br</a>
                                </p>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """
def obter_coordenadas_por_endereco(endereco_completo, cidade, estado):
    """
    Obtém latitude e longitude a partir de endereço usando OpenStreetMap Nominatim API
    
    Args:
        endereco_completo: Rua, número, bairro (opcional)
        cidade: Nome da cidade
        estado: Sigla do estado (ES, BA, SP, etc)
    
    Returns:
        tuple: (latitude, longitude) ou (None, None) se não encontrar
    """
    try:
        import time
        
        # Monta endereço completo para busca
        if endereco_completo and endereco_completo.strip():
            query = f"{endereco_completo}, {cidade}, {estado}, Brasil"
        else:
            query = f"{cidade}, {estado}, Brasil"
        
        print(f"\n{'='*60}")
        print(f"🌍 GEOCODING - Buscando coordenadas")
        print(f"{'='*60}")
        print(f"Endereço: {query}")
        
        # API Nominatim do OpenStreetMap (gratuita)
        url = "https://nominatim.openstreetmap.org/search"
        
        headers = {
            'User-Agent': 'MedPIX/1.0 (alex.oceano@gmail.com)'  # Obrigatório pela política do OSM
        }
        
        params = {
            'q': query,
            'format': 'json',
            'limit': 1,
            'countrycodes': 'br'  # Limita ao Brasil
        }
        
        response = requests.get(url, params=params, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            if data and len(data) > 0:
                lat = float(data[0]['lat'])
                lon = float(data[0]['lon'])
                display_name = data[0].get('display_name', '')
                
                print(f"✅ Coordenadas encontradas:")
                print(f"   Latitude: {lat}")
                print(f"   Longitude: {lon}")
                print(f"   Local: {display_name}")
                print(f"{'='*60}\n")
                
                # Pausa de 1 segundo (respeitar limites da API)
                time.sleep(1)
                
                return lat, lon
            else:
                print(f"⚠️ Nenhum resultado encontrado para: {query}")
                print(f"{'='*60}\n")
                return None, None
        else:
            print(f"❌ Erro na API: Status {response.status_code}")
            print(f"{'='*60}\n")
            return None, None
            
    except Exception as e:
        print(f"❌ Erro ao obter coordenadas: {e}")
        import traceback
        traceback.print_exc()
        return None, None

def notificar_cliente_pagamento_confirmado(venda_data, cliente_data, clinica_data):
    """Notifica cliente após confirmação de pagamento"""
    from datetime import timedelta
    
    try:
        # Calcula data de vencimento (30 dias)
        data_confirmacao = datetime.strptime(venda_data['data_pagamento_confirmado'], '%Y-%m-%dT%H:%M:%S')
        data_vencimento = (data_confirmacao + timedelta(days=30)).strftime('%d/%m/%Y')
        
        nome_cliente = cliente_data['nome_completo'].split()[0]
        clinica_nome = clinica_data.get('nome_fantasia', clinica_data.get('razao_social'))
        clinica_whatsapp = clinica_data.get('whatsapp', '-')
        clinica_endereco = f"{clinica_data.get('endereco_rua', '')}, {clinica_data.get('endereco_cidade', '')}/{clinica_data.get('endereco_estado', '')}"
        
        # EMAIL
        assunto = "🎉 Pagamento Confirmado! Você tem 30 dias para agendar"
        
        conteudo_html = f"""
            <h2 style="color: #10b981; margin-top: 0;">Pagamento Confirmado!</h2>
            <p style="font-size: 16px; line-height: 1.6;">
                Olá, <strong>{nome_cliente}</strong>!
            </p>
            <p style="font-size: 16px; line-height: 1.6;">
                Seu pagamento foi confirmado com sucesso! 🎉
            </p>
            
            <div style="background-color: #f0fdf4; border-left: 4px solid #10b981; padding: 20px; margin: 20px 0; border-radius: 5px;">
                <h3 style="margin-top: 0; color: #15803d;">Próximos Passos</h3>
                <p style="margin: 10px 0;">
                    ⏰ Você tem até <strong>{data_vencimento}</strong> para agendar seu atendimento<br>
                    📱 Entre em contato com a clínica<br>
                    🎯 Sem pressão - escolha a melhor data para você!
                </p>
            </div>
            
            <div style="background-color: #eff6ff; padding: 20px; margin: 20px 0; border-radius: 5px;">
                <h3 style="margin-top: 0; color: #1e40af;">Dados da Clínica</h3>
                <p style="margin: 5px 0;"><strong>Nome:</strong> {clinica_nome}</p>
                <p style="margin: 5px 0;"><strong>WhatsApp:</strong> {clinica_whatsapp}</p>
                <p style="margin: 5px 0;"><strong>Endereço:</strong> {clinica_endereco}</p>
            </div>
            
            <div style="background-color: #fef3c7; padding: 20px; margin: 20px 0; border-radius: 5px;">
                <h3 style="margin-top: 0; color: #92400e;">💰 Seu Cashback</h3>
                <p style="margin: 5px 0;">
                    Após a conclusão do atendimento, você receberá cashback diretamente na sua conta PIX!
                </p>
            </div>
        """
        
        enviar_email(
            destinatario=cliente_data.get('email'),
            assunto=assunto,
            corpo_html=template_email_base("Pagamento Confirmado", conteudo_html, "#10b981")
        )
        
        # WHATSAPP
        mensagem_whatsapp = f"""
🎉 *Pagamento Confirmado!*

Olá, *{nome_cliente}*!

Seu pagamento foi confirmado com sucesso!

━━━━━━━━━━━━━━━━━━━━
⏰ *IMPORTANTE*
Você tem até *{data_vencimento}* para agendar

━━━━━━━━━━━━━━━━━━━━
🏥 *CLÍNICA*
{clinica_nome}
📱 {clinica_whatsapp}

━━━━━━━━━━━━━━━━━━━━
💰 *CASHBACK*
Você receberá cashback após o atendimento!

_Mensagem enviada via MedPIX_
        """
        
        enviar_whatsapp(
            numero=cliente_data.get('telefone'),
            mensagem=mensagem_whatsapp
        )
        
        print(f"✅ Notificações enviadas para cliente {nome_cliente}")
        
    except Exception as e:
        print(f"❌ Erro ao notificar cliente: {e}")


def notificar_clinica_nova_venda(venda_data, cliente_data, clinica_data, itens):
    """Notifica clínica sobre nova venda"""
    from datetime import timedelta
    
    try:
        data_vencimento = (datetime.now() + timedelta(days=30)).strftime('%d/%m/%Y')
        
        nome_cliente = cliente_data['nome_completo']
        cpf_cliente = cliente_data.get('cpf', '')
        tel_cliente = cliente_data.get('telefone', '')
        
        # Monta lista de procedimentos
        procedimentos_html = "<ul style='margin: 10px 0; padding-left: 20px;'>"
        procedimentos_lista = []
        for item in itens:
            procedimentos_html += f"<li>{item['nome']} (Qtd: {item['quantidade']})</li>"
            procedimentos_lista.append(f"• {item['nome']} (Qtd: {item['quantidade']})")
        procedimentos_html += "</ul>"
        
        # EMAIL
        assunto = f"🎉 Nova Venda! Cliente: {nome_cliente}"
        
        conteudo_html = f"""
            <h2 style="color: #10b981; margin-top: 0;">Nova Venda Confirmada!</h2>
            
            <div style="background-color: #f0fdf4; border-left: 4px solid #10b981; padding: 20px; margin: 20px 0; border-radius: 5px;">
                <h3 style="margin-top: 0; color: #15803d;">Dados do Cliente</h3>
                <p style="margin: 5px 0;"><strong>Nome:</strong> {nome_cliente}</p>
                <p style="margin: 5px 0;"><strong>CPF:</strong> {cpf_cliente}</p>
                <p style="margin: 5px 0;"><strong>Telefone:</strong> {tel_cliente}</p>
            </div>
            
            <div style="background-color: #eff6ff; padding: 20px; margin: 20px 0; border-radius: 5px;">
                <h3 style="margin-top: 0; color: #1e40af;">Procedimentos</h3>
                {procedimentos_html}
            </div>
            
            <div style="background-color: #fef3c7; padding: 20px; margin: 20px 0; border-radius: 5px;">
                <h3 style="margin-top: 0; color: #92400e;">⏰ Agendamento</h3>
                <p style="margin: 5px 0;">
                    Cliente tem até <strong>{data_vencimento}</strong> para agendar<br>
                    Aguarde contato do cliente!
                </p>
            </div>
            
            <div style="background-color: #dcfce7; padding: 20px; margin: 20px 0; border-radius: 5px;">
                <h3 style="margin-top: 0; color: #15803d;">💰 Pagamento</h3>
                <p style="margin: 5px 0;">
                    <strong>Parcela 1 (50%):</strong> Disponível para pagamento agora!<br>
                    <strong>Parcela 2 (50%):</strong> Após conclusão dos atendimentos
                </p>
            </div>
        """
        
        enviar_email(
            destinatario=clinica_data.get('email'),
            assunto=assunto,
            corpo_html=template_email_base("Nova Venda", conteudo_html, "#10b981")
        )
        
        # WHATSAPP
        mensagem_whatsapp = f"""
🎉 *NOVA VENDA!*

━━━━━━━━━━━━━━━━━━━━
👤 *CLIENTE*
Nome: {nome_cliente}
CPF: {cpf_cliente}
📱 {tel_cliente}

━━━━━━━━━━━━━━━━━━━━
🔬 *PROCEDIMENTOS*
{chr(10).join(procedimentos_lista)}

━━━━━━━━━━━━━━━━━━━━
⏰ *AGENDAMENTO*
Cliente tem até *{data_vencimento}*
Aguarde contato dele!

━━━━━━━━━━━━━━━━━━━━
💰 *PAGAMENTO*
Parcela 1: Disponível AGORA
Parcela 2: Após atendimentos

_Mensagem enviada via MedPIX_
        """
        
        enviar_whatsapp(
            numero=clinica_data.get('whatsapp'),
            mensagem=mensagem_whatsapp
        )
        
        print(f"✅ Notificações enviadas para clínica")
        
    except Exception as e:
        print(f"❌ Erro ao notificar clínica: {e}")


def verificar_prazos_pendentes():
    """
    Verifica vendas pendentes e envia alertas automáticos
    Esta função deve ser executada DIARIAMENTE
    """
    try:
        if not supabase:
            print("⚠️ Supabase não configurado")
            return
        
        print("🔍 Verificando prazos pendentes...")
        
        # Busca vendas com pagamento confirmado mas não totalmente atendidas
        vendas = supabase.table('vendas').select(
            '*, clientes(*), clinicas(*), itens_venda(*)'
        ).eq('pagamento_confirmado', True).execute()
        
        hoje = datetime.now()
        alertas_enviados = 0
        
        for venda in vendas.data if vendas.data else []:
            # Pula se todos itens já foram atendidos
            itens = venda.get('itens_venda', [])
            if not itens:
                continue
                
            itens_atendidos = [i for i in itens if i.get('atendido')]
            if len(itens) == len(itens_atendidos):
                continue
            
            # Calcula dias desde confirmação
            data_confirmacao_str = venda.get('data_pagamento_confirmado')
            if not data_confirmacao_str:
                continue
                
            data_confirmacao = datetime.strptime(
                data_confirmacao_str, 
                '%Y-%m-%dT%H:%M:%S'
            )
            dias_passados = (hoje - data_confirmacao).days
            
            cliente = venda.get('clientes', {})
            clinica = venda.get('clinicas', {})
            
            # Alerta de 7 dias antes (23 dias após confirmação)
            if dias_passados == 23:
                print(f"📧 Enviando alerta 7 dias para {cliente.get('nome_completo')}")
                # Implementar função notificar_cliente_lembrete_7_dias
                alertas_enviados += 1
            
            # Alerta de 1 dia antes (29 dias após confirmação)
            elif dias_passados == 29:
                print(f"🚨 Enviando alerta 1 dia para {cliente.get('nome_completo')}")
                # Implementar função notificar_cliente_lembrete_1_dia
                alertas_enviados += 1
            
            # Vencido (30+ dias)
            elif dias_passados >= 30:
                print(f"⚠️ Venda vencida: {cliente.get('nome_completo')}")
                # Implementar função notificar_venda_vencida
        
        print(f"✅ Verificação concluída - {alertas_enviados} alertas enviados")
        
    except Exception as e:
        print(f"❌ Erro ao verificar prazos: {e}")
        import traceback
        traceback.print_exc()

def iniciar_verificacao_periodica():
    def loop_verificacao():
        while True:
            try:
                verificar_e_deletar_vendas_expiradas()
            except Exception as e:
                print(f"⚠️ Erro na verificação periódica: {e}")
            time.sleep(300)  # 5 minutos
    
    thread = threading.Thread(target=loop_verificacao, daemon=True)
    thread.start()
    print("✅ Thread de verificação periódica iniciada")

# Iniciar automaticamente
iniciar_verificacao_periodica()

def gerar_codigo_venda_com_beneficiario(cliente_id, beneficiario_nome, beneficiario_cpf, tipo_compra):
    """Gera código com dados do beneficiário: AAAA-NNNN-CCCC-TTTT"""
    
    ano = datetime.now().strftime("%Y")
    nome_limpo = re.sub(r'[^A-Za-z]', '', beneficiario_nome.upper())
    iniciais_nome = nome_limpo[:4].ljust(4, 'X')
    cpf_limpo = re.sub(r'\D', '', beneficiario_cpf)
    ultimos_cpf = cpf_limpo[-4:].zfill(4)
    timestamp = str(int(datetime.now().timestamp()))[-4:]
    
    return f"{ano}-{iniciais_nome}-{ultimos_cpf}-{timestamp}"

# ==================== INTERFACE ====================

app_ui = ui.page_fluid(
    ui.tags.script("""
        // Captura parâmetros da URL e envia para o Shiny
        window.addEventListener('DOMContentLoaded', function() {
            const urlParams = new URLSearchParams(window.location.search);
            const view = urlParams.get('view');
            const clinic_id = urlParams.get('clinic_id');
            
            console.log('🔍 JavaScript - Parâmetros capturados:', {view, clinic_id});
            
            if (view || clinic_id) {
                // Aguarda o Shiny estar pronto
                setTimeout(function() {
                    if (typeof Shiny !== 'undefined') {
                        Shiny.setInputValue('url_view_param', view, {priority: 'event'});
                        Shiny.setInputValue('url_clinic_id_param', clinic_id, {priority: 'event'});
                        console.log('✅ Parâmetros enviados para o Shiny');
                    }
                }, 100);
            }
        });
    """),
    ui.tags.head(
        ui.tags.style("""
            body { background: linear-gradient(135deg, #1DD1A1 0%, #0D9488 100%);
                    min-height: 100vh; font-family: 'Segoe UI', sans-serif; }
            .app-header { background: #2D3748; backdrop-filter: blur(10px);
                          padding: 1rem 2rem; border-radius: 1rem; margin-bottom: 2rem;
                          box-shadow: 0 8px 32px rgba(0,0,0,0.1); }
            .app-title { font-size: 2.5rem; font-weight: 800;
                         color: #1DD1A1;
                         margin: 0; }
            .card-custom { background: rgba(255,255,255,0.95); backdrop-filter: blur(10px);
                           border-radius: 1rem; padding: 2rem;
                           box-shadow: 0 8px 32px rgba(0,0,0,0.1); margin-bottom: 1.5rem; }
            .btn-primary { background: linear-gradient(135deg, #1DD1A1, #0D9488); border: none;
                           padding: 0.75rem 2rem; border-radius: 0.5rem; font-weight: 600;
                           color: white; transition: all 0.3s; }
            .btn-primary:hover { transform: translateY(-2px);
                                 box-shadow: 0 8px 16px rgba(102, 126, 234, 0.4); }
            .stat-card { background: #2D3748;
                         border-radius: 1rem; padding: 2rem; color: white;
                         box-shadow: 0 8px 32px rgba(0,0,0,0.1); text-align: center;
                         transition: all 0.3s; 
                         border: 2px solid #1DD1A1; }
            .stat-card:hover { transform: translateY(-5px);
                               box-shadow: 0 12px 48px rgba(0,0,0,0.15); }
            .stat-value { font-size: 2.5rem; font-weight: bold; }
            .stat-label { font-size: 1rem; opacity: 0.9; margin-top: 0.5rem; }
            /* ========== MOBILE OPTIMIZATIONS ========== */
            @media (max-width: 768px) {
                .stat-card { 
                    padding: 1.25rem !important; 
                    margin-bottom: 1rem !important;
                }
                .stat-value { 
                    font-size: 2rem !important; 
                }
                .stat-label { 
                    font-size: 0.85rem !important; 
                }
                .card-custom { 
                    padding: 1.25rem !important; 
                }
                .app-title { 
                    font-size: 1.75rem !important; 
                }
                h2 { 
                    font-size: 1.5rem !important; 
                }
                h3 { 
                    font-size: 1.25rem !important; 
                }
                h4 { 
                    font-size: 1.1rem !important; 
                }
                .app-header {
                    padding: 1rem !important;
                }
                .app-header h4 {
                    font-size: 1.1rem !important;
                }
                .app-header p {
                    font-size: 0.85rem !important;
                }
                .app-header img {
                    height: 50px !important;
                }
                .btn-primary { 
                    padding: 0.6rem 1.5rem !important; 
                    font-size: 0.95rem !important;
                }
                .form-control, .form-select { 
                    padding: 0.6rem !important; 
                    font-size: 0.95rem !important;
                }
                body {
                    font-size: 0.95rem !important;
                }
            }

            @media (max-width: 480px) {
                .stat-card { 
                    padding: 1rem !important; 
                }
                .stat-value { 
                    font-size: 1.75rem !important; 
                }
                .stat-label { 
                    font-size: 0.8rem !important; 
                }
                .card-custom { 
                    padding: 1rem !important; 
                }
            }
            .form-control, .form-select { border-radius: 0.5rem; border: 2px solid #e2e8f0;
                                           padding: 0.75rem; transition: all 0.3s; }
            .form-control:focus, .form-select:focus { border-color: #1DD1A1;
                                                      box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1); }
            .nav-pills .nav-link { border-radius: 0.5rem; padding: 0.75rem 1.5rem;
                                   margin: 0.25rem; transition: all 0.3s; font-weight: 600; }
            .nav-pills .nav-link.active { background: linear-gradient(135deg, #1DD1A1, #0D9488);
                                           color: white; }
        """),
        # ============================================================
        # ADICIONANDO O BLOCO DE SCRIPT AQUI
        # ============================================================
        ui.tags.script(r"""
            // ============================================================
            // FUNÇÃO AUXILIAR: VALIDAR CPF
            // ============================================================
            function validarCPF(cpf) {
                if (typeof cpf !== 'string') return false; // Garante que é string
                cpf = cpf.replace(/[^0-9]/g, ''); // Remove não dígitos
                
                if (cpf.length !== 11) return false;
                if (/^(\d)\1{10}$/.test(cpf)) return false; // Verifica dígitos iguais
                
                let soma = 0;
                for (let i = 0; i < 9; i++) {
                    soma += parseInt(cpf[i]) * (10 - i);
                }
                let resto = soma % 11;
                let digito1 = resto < 2 ? 0 : 11 - resto;
                
                if (parseInt(cpf[9]) !== digito1) return false;
                
                soma = 0;
                for (let i = 0; i < 10; i++) {
                    soma += parseInt(cpf[i]) * (11 - i);
                }
                resto = soma % 11;
                let digito2 = resto < 2 ? 0 : 11 - resto;
                
                return parseInt(cpf[10]) === digito2;
            }

            // ============================================================
            // GARANTE QUE O CÓDIGO RODE APÓS O SHINY CARREGAR
            // ============================================================
            // Usamos um observer do Shiny para garantir que os elementos existam
            // quando tentarmos adicionar os event listeners.
            Shiny.addCustomMessageHandler('initialize_validations', function(message) {
                console.log("Inicializando validações de formulário...");

                // ============================================================
                // VALIDAÇÃO DE CPF EM TEMPO REAL
                // ============================================================
                const cpfInput = document.getElementById('cadastro_cpf');

                if (cpfInput) {
                    console.log("Input CPF encontrado.");
                    cpfInput.addEventListener('input', function(e) {
                        let value = e.target.value.replace(/\\D/g, ''); // Remove não dígitos

                        // Formata automaticamente (máscara)
                        let formattedValue = value;
                        if (value.length > 9) {
                            formattedValue = value.replace(/(\\d{3})(\\d{3})(\\d{3})(\\d{2})/, '$1.$2.$3-$4');
                        } else if (value.length > 6) {
                            formattedValue = value.replace(/(\\d{3})(\\d{3})(\\d{1,3})/, '$1.$2.$3');
                        } else if (value.length > 3) {
                            formattedValue = value.replace(/(\\d{3})(\\d{1,3})/, '$1.$2');
                        }
                        // Limita ao tamanho máximo formatado
                        if (formattedValue.length > 14) {
                             formattedValue = formattedValue.substring(0, 14);
                        }
                        e.target.value = formattedValue;


                        // Visual feedback da validação
                        const digits = value.replace(/\\D/g, ''); // Pega só os dígitos novamente
                        if (digits.length === 11) {
                            if (validarCPF(digits)) {
                                e.target.style.borderColor = '#10b981'; // Verde
                                e.target.style.boxShadow = '0 0 0 3px rgba(16, 185, 129, 0.1)';
                            } else {
                                e.target.style.borderColor = '#ef4444'; // Vermelho
                                e.target.style.boxShadow = '0 0 0 3px rgba(239, 68, 68, 0.1)';
                            }
                        } else if (digits.length > 0) {
                            // Se não tem 11 dígitos, mas tem algo, marca como inválido (vermelho)
                            e.target.style.borderColor = '#ef4444';
                            e.target.style.boxShadow = '0 0 0 3px rgba(239, 68, 68, 0.1)';
                        }
                        else {
                            // Reseta o estilo se o campo estiver vazio
                            e.target.style.borderColor = '#e2e8f0'; // Cor padrão
                            e.target.style.boxShadow = 'none';
                        }
                    });
                } else {
                    console.log("Input CPF 'cadastro_cpf' NÃO encontrado.");
                }

                // ============================================================
                // VALIDAÇÃO DE EMAIL EM TEMPO REAL (ao sair do campo)
                // ============================================================
                const emailInput = document.getElementById('cadastro_email');

                if (emailInput) {
                    console.log("Input Email encontrado.");
                    emailInput.addEventListener('blur', function(e) {
                        const email = e.target.value.trim();
                        // Regex um pouco mais flexível
                        const emailRegex = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;

                        if (email.length > 0) {
                            if (emailRegex.test(email)) {
                                e.target.style.borderColor = '#10b981'; // Verde
                                e.target.style.boxShadow = '0 0 0 3px rgba(16, 185, 129, 0.1)';
                            } else {
                                e.target.style.borderColor = '#ef4444'; // Vermelho
                                e.target.style.boxShadow = '0 0 0 3px rgba(239, 68, 68, 0.1)';
                            }
                        } else {
                             // Reseta se sair do campo vazio
                             e.target.style.borderColor = '#e2e8f0';
                             e.target.style.boxShadow = 'none';
                        }
                    });
                     // Validação inicial caso o campo já tenha valor (ex: preenchimento automático)
                    emailInput.dispatchEvent(new Event('blur'));
                } else {
                     console.log("Input Email 'cadastro_email' NÃO encontrado.");
                }

                // ============================================================
                // VALIDAÇÃO DE SENHAS COINCIDENTES
                // ============================================================
                const senhaInput = document.getElementById('cadastro_senha');
                const senhaConfirmaInput = document.getElementById('cadastro_senha_confirma');

                function validarSenhasCoincidentes() {
                    const senha = senhaInput?.value || '';
                    const confirma = senhaConfirmaInput?.value || '';

                    if (!senhaConfirmaInput) return; // Sai se o campo de confirmação não existe

                    if (confirma.length > 0) {
                        if (senha === confirma && senha.length > 0) { // Adicionado senha.length > 0
                            senhaConfirmaInput.style.borderColor = '#10b981'; // Verde
                            senhaConfirmaInput.style.boxShadow = '0 0 0 3px rgba(16, 185, 129, 0.1)';
                        } else {
                            senhaConfirmaInput.style.borderColor = '#ef4444'; // Vermelho
                            senhaConfirmaInput.style.boxShadow = '0 0 0 3px rgba(239, 68, 68, 0.1)';
                        }
                    } else {
                         // Reseta se o campo de confirmação estiver vazio
                         senhaConfirmaInput.style.borderColor = '#e2e8f0';
                         senhaConfirmaInput.style.boxShadow = 'none';
                    }
                }

                if (senhaInput) {
                     console.log("Input Senha encontrado.");
                     senhaInput.addEventListener('input', validarSenhasCoincidentes);
                } else {
                     console.log("Input Senha 'cadastro_senha' NÃO encontrado.");
                }
                if (senhaConfirmaInput) {
                     console.log("Input Confirma Senha encontrado.");
                     senhaConfirmaInput.addEventListener('input', validarSenhasCoincidentes);
                     // Validação inicial
                     validarSenhasCoincidentes();
                } else {
                     console.log("Input Confirma Senha 'cadastro_senha_confirma' NÃO encontrado.");
                }


                // ============================================================
                // FORÇA DA SENHA
                // ============================================================
                if (senhaInput) {
                    senhaInput.addEventListener('input', function(e) {
                        const senha = e.target.value;
                        let forca = 0;

                        // Critérios de força (simplificados)
                        if (senha.length >= 6) forca++; // Mínimo 6 caracteres
                        if (senha.length >= 8) forca++; // Ideal 8+
                        if (/[a-z]/.test(senha)) forca++; // Letra minúscula
                        if (/[A-Z]/.test(senha)) forca++; // Letra maiúscula
                        if (/[0-9]/.test(senha)) forca++; // Número
                        if (/[^a-zA-Z0-9]/.test(senha)) forca++; // Símbolo

                        let cor, texto;
                        if (senha.length == 0) { // Se vazio, não mostra nada
                             forca = -1; // Flag para esconder
                        } else if (forca <= 2) {
                            cor = '#ef4444'; // Vermelho
                            texto = '❌ Fraca';
                        } else if (forca <= 4) {
                            cor = '#f59e0b'; // Laranja
                            texto = '⚠️ Média';
                        } else {
                            cor = '#10b981'; // Verde
                            texto = '✅ Forte';
                        }

                        // Cria ou atualiza o elemento indicador de força
                        let indicador = document.getElementById('senha_forca_indicador');
                        if (!indicador) {
                            indicador = document.createElement('small');
                            indicador.id = 'senha_forca_indicador';
                            indicador.style.display = 'block';
                            indicador.style.marginTop = '0.25rem'; // Ajuste fino da posição
                            indicador.style.marginBottom = '1rem';
                            indicador.style.fontWeight = '600';
                            indicador.style.fontSize = '0.8rem';
                            // Insere logo após o campo de senha
                            e.target.parentNode.insertBefore(indicador, e.target.nextSibling);
                        }

                        if (forca >= 0) { // Mostra apenas se a senha não estiver vazia
                            indicador.style.color = cor;
                            indicador.textContent = `Força: ${texto}`;
                        } else {
                            indicador.textContent = ''; // Limpa se a senha estiver vazia
                        }
                    });
                     // Dispara o evento inicial para checar a força caso haja valor pré-preenchido
                     senhaInput.dispatchEvent(new Event('input'));
                } else {
                     console.log("Input Senha 'cadastro_senha' NÃO encontrado para força.");
                }

                console.log("Validações de formulário inicializadas.");
            }); // Fim do Shiny.addCustomMessageHandler
        """), # Fim do ui.tags.script
        
# === ADICIONE ESTE SCRIPT ===
        ui.tags.script(r"""
            async function shareOnWhatsApp(downloadUrl, textMessage, filename, fallbackUrl) {
                console.log("Iniciando compartilhamento...");
                console.log("URL Imagem:", downloadUrl);
                console.log("Nome Arquivo:", filename);
                console.log("Fallback URL:", fallbackUrl);

                // Texto para o alerta de fallback
                const fallbackAlert = "⚠️ Seu navegador não suporta anexo automático.\n\n" +
                                      "1. Estamos baixando a imagem para você.\n" +
                                      "2. A conversa do WhatsApp será aberta.\n" +
                                      "3. Anexe a imagem que você acabou de baixar na conversa.";

                if (navigator.share) {
                    try {
                        // 1. Tenta buscar a imagem do servidor
                        const response = await fetch(downloadUrl);
                        const blob = await response.blob();
                        const file = new File([blob], filename, { type: 'image/png' });

                        // 2. Verifica se o navegador pode compartilhar este arquivo
                        if (navigator.canShare && navigator.canShare({ files: [file] })) {
                            // 3. Abre a janela de compartilhamento nativa
                            await navigator.share({
                                files: [file],
                                text: textMessage,
                                title: 'Detalhes da Compra MedPIX'
                            });
                            console.log('Compartilhado com sucesso via Web Share API!');
                        } else {
                            // Navegador não pode compartilhar arquivos (ex: Chrome Desktop no Mac)
                            console.warn('Web Share API não suporta arquivos neste navegador. Usando fallback.');
                            alert(fallbackAlert);
                            window.open(fallbackUrl, '_blank'); // Abre WhatsApp (texto)
                            // Dispara o download manual
                            const a = document.createElement('a');
                            a.href = downloadUrl;
                            a.download = filename;
                            document.body.appendChild(a);
                            a.click();
                            document.body.removeChild(a);
                        }
                    } catch (err) {
                        if (err.name === 'AbortError') {
                            console.log('Compartilhamento cancelado pelo usuário.');
                        } else {
                            console.error('Erro no Web Share API:', err);
                            // Se falhar, usa o fallback
                            alert(fallbackAlert);
                            window.open(fallbackUrl, '_blank');
                            const a = document.createElement('a');
                            a.href = downloadUrl;
                            a.download = filename;
                            document.body.appendChild(a);
                            a.click();
                            document.body.removeChild(a);
                        }
                    }
                } else {
                    // Navegador não tem Web Share API (ex: Firefox Desktop)
                    console.warn('Web Share API não disponível. Usando fallback.');
                    alert(fallbackAlert);
                    window.open(fallbackUrl, '_blank'); // Abre WhatsApp (texto)
                    // Dispara o download manual
                    const a = document.createElement('a');
                    a.href = downloadUrl;
                    a.download = filename;
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                }
            }
        """)
    ), # Fim do ui.tags.head
    ui.output_ui("main_content")
)



# ==================== SERVIDOR ====================

def server(input: Inputs, output: Outputs, session: Session):
    
    # ==========================================================
    # === ADICIONE ESTE BLOCO NO TOPO DA FUNÇÃO SERVER ===
    # ==========================================================
    @reactive.calc
    def get_url_params():
        """Lê os parâmetros da URL de forma confiável"""
        resultado = {"view": None, "clinic_id": None}
        
        try:
            # Método 1: Via input JavaScript (se disponível)
            if hasattr(input, 'url_view_param'):
                view_js = input.url_view_param()
                if view_js:
                    resultado["view"] = view_js
                    
            if hasattr(input, 'url_clinic_id_param'):
                clinic_js = input.url_clinic_id_param()
                if clinic_js:
                    resultado["clinic_id"] = clinic_js
            
            # Se pegou via JS, retorna
            if resultado["view"] or resultado["clinic_id"]:
                print(f"✅ URL Params (JavaScript): {resultado}")
                return resultado
            
            # Método 2: Via session (funciona no Render)
            try:
                # Tenta acessar via diferentes atributos do session
                if hasattr(session, 'http_conn'):
                    if hasattr(session.http_conn, 'scope'):
                        scope = session.http_conn.scope
                        query_string = scope.get('query_string', b'').decode('utf-8')
                        if query_string:
                            params = urllib.parse.parse_qs(query_string)
                            resultado["view"] = params.get('view', [None])[0]
                            resultado["clinic_id"] = params.get('clinic_id', [None])[0]
                            print(f"✅ URL Params (Scope): {resultado}")
                            return resultado
            except Exception as e:
                print(f"⚠️ Método scope falhou: {e}")
            
            # Método 3: Via request.query_params
            try:
                request = session.http_conn.request
                query_params = dict(request.query_params)
                resultado["view"] = query_params.get('view')
                resultado["clinic_id"] = query_params.get('clinic_id')
                if resultado["view"] or resultado["clinic_id"]:
                    print(f"✅ URL Params (Request): {resultado}")
                    return resultado
            except Exception as e:
                print(f"⚠️ Método request falhou: {e}")
            
            print(f"⚠️ Nenhum método funcionou. Resultado: {resultado}")
            
        except Exception as e:
            print(f"❌ Erro geral ao ler URL params: {e}")
            import traceback
            traceback.print_exc()
        
        return resultado
    # ==========================================================
    
    
    # ========== SCHEDULER DE ALERTAS AUTOMÁTICOS ==========
    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(
        verificar_prazos_pendentes,
        'cron',
        hour=9,  # Executa todo dia às 9h da manhã
        minute=0
    )
    scheduler.start()
    
    # Garante que o scheduler será fechado ao encerrar
    atexit.register(lambda: scheduler.shutdown())
    
    print("✅ Scheduler de alertas iniciado - verificação diária às 9h")
    
 
 
# ========== VARIÁVEIS REATIVAS ========== 

    user_data = reactive.Value(None)
    cliente_logado = reactive.Value(None)
    info_whatsapp_data = reactive.Value(None)
    carrinho = reactive.Value([])
    ultimo_contrato = reactive.Value(None)
    data_changed_trigger = reactive.Value(0)
    venda_atual = reactive.Value(None)
    itens_atendimento = reactive.Value([])
    ultima_venda_pdf = reactive.Value(None)
    venda_selecionada_pagamento = reactive.Value(None)
    venda_id_para_pagamento = reactive.Value(None)
    atendimento_trigger = reactive.Value(0)
    carrinho_cliente = reactive.Value([])
    busca_procedimentos = reactive.Value([])
    carrinho_cliente_trigger = reactive.Value(0)
    minhas_compras_trigger = reactive.Value(0)
    venda_id_para_comprovante = reactive.Value(None)
    tela_atual = reactive.Value("login")
    compras_trigger = reactive.Value(0)
    cliente_viu_clinica_id = reactive.Value(None)
    cashback_trigger = reactive.Value(0)
    cashback_aguardando_trigger = reactive.Value(0)
    pacote_editando_id = reactive.Value(None)
    pacote_valores_base = reactive.Value({})


    
    
    pdf_trigger = reactive.Value(0)
    
    # ========== TRIGGERS (gatilhos) DE ATUALIZAÇÃO DE TABELAS ==========
    
    procedimentos_trigger = reactive.Value(0)
    pacotes_trigger = reactive.Value(0)
    clientes_trigger = reactive.Value(0)
    clinicas_trigger = reactive.Value(0)
    clinica_editando_id = reactive.Value(None)  

    # ========================================================
    
    
    # Login
    @reactive.Effect
    @reactive.event(input.btn_login)
    def login():
        try:
            documento = input.login_documento()
            senha = input.login_senha()
            
            print("\n" + "="*60)
            print("🔍 DEBUG DE LOGIN E SENHA")
            print("="*60)
            
            if not documento or not senha:
                ui.notification_show("⚠️ Preencha CPF/CNPJ e senha!", type="warning")
                return
            
            if not supabase:
                ui.notification_show("❌ Erro: Supabase não configurado!", type="error")
                return
            
            # Limpa documento
            doc_limpo = limpar_documento(documento)
            print(f"📄 Documento digitado: '{documento}'")
            print(f"📄 Documento limpo: '{doc_limpo}'")
            
            # Valida formato
            if len(doc_limpo) == 11:
                if not validar_cpf(doc_limpo):
                    ui.notification_show("⚠️ CPF inválido!", type="warning")
                    return
                print("✅ CPF válido (11 dígitos)")
            elif len(doc_limpo) == 14:
                if not validar_cnpj(doc_limpo):
                    ui.notification_show("⚠️ CNPJ inválido!", type="warning")
                    return
                print("✅ CNPJ válido (14 dígitos)")
            else:
                ui.notification_show("⚠️ Digite um CPF (11 dígitos) ou CNPJ (14 dígitos)!", type="warning")
                return
            
            # Busca usuário
            print(f"\n🔍 Buscando usuário no banco...")
            result = supabase.table('usuarios').select('*').eq('cpf', doc_limpo).eq('ativo', True).execute()
            
            if not result.data:
                print(f"❌ Nenhum usuário encontrado com CPF: {doc_limpo}")
                ui.notification_show(f"❌ Usuário não encontrado!", type="error")
                return
            
            usuario = result.data[0]
            print(f"✅ Usuário encontrado!")
            print(f"   Nome: {usuario.get('nome')}")
            print(f"   Tipo: {usuario.get('tipo_usuario')}")
            
            # Validação de senha - DEBUG DETALHADO
            print(f"\n🔐 VALIDAÇÃO DE SENHA:")
            print(f"   Senha digitada (RAW): {repr(senha)}")
            print(f"   Tipo da senha: {type(senha)}")
            print(f"   Tamanho: {len(senha)} caracteres")
            
            senha_hash_banco = usuario.get('senha_hash', '')
            print(f"   Hash no banco: {senha_hash_banco[:30] if senha_hash_banco else '(vazio)'}...")
            
            # Verifica se tem hash
            if not senha_hash_banco or senha_hash_banco == '':
                print("⚠️ Usuário SEM senha_hash no banco!")
                user_data.set(usuario)
                ui.notification_show(
                    f"✅ Bem-vindo, {usuario['nome']}!\n⚠️ Configure uma senha.",
                    type="message"
                )
                print("="*60 + "\n")
                return
            
            # ✅ USA A FUNÇÃO hash_senha() AO INVÉS DE FAZER MANUALMENTE
            try:
                # Remove espaços extras que possam vir do input
                senha_limpa = senha.strip()
                
                print(f"\n🔍 DEBUG EXTRA:")
                print(f"   Senha após strip: '{senha_limpa}'")
                print(f"   Tamanho após strip: {len(senha_limpa)}")
                
                # Gera hash usando a MESMA função do cadastro
                senha_hash_digitada = hash_senha(senha_limpa)
                
                print(f"\n   Hash gerado da senha digitada: {senha_hash_digitada[:30]}...")
                print(f"   Hash do banco:                 {senha_hash_banco[:30]}...")
                
                # Compara
                print(f"\n🔍 Comparando hashes:")
                print(f"   Hash digitada == Hash banco? {senha_hash_digitada == senha_hash_banco}")
                
                if senha_hash_digitada == senha_hash_banco:
                    print("✅ SENHA CORRETA! Login OK!")
                    user_data.set(usuario)                   
# Se for um cliente, busca os dados da tabela 'clientes'
                    if usuario.get('tipo_usuario') == 'cliente':
                        try:
                            cliente_res = supabase.table('clientes').select('*').eq('usuario_id', usuario['id']).single().execute()
                            if cliente_res.data:
                                cliente_logado.set(cliente_res.data)
                                print(f"✅ Dados do cliente carregados: {cliente_res.data.get('nome_completo')}")
                            else:
                                cliente_logado.set(None)
                                print(f"⚠️ Usuário cliente logado, mas sem registro na tabela 'clientes'.")
                        except Exception as e:
                            print(f"❌ Erro ao buscar dados do cliente: {e}")
                            cliente_logado.set(None)
                    else:
                        # Garante que está limpo se for clínica/admin
                        cliente_logado.set(None)
                    ui.notification_show(f"✅ Bem-vindo, {usuario['nome']}!", type="message", duration=2)
                else:
                    print("❌ SENHA INCORRETA!")
                    print(f"\n💡 TESTE DE VALIDAÇÃO:")
                    print(f"   Hash de 'senha123' deveria ser:")
                    print(f"   {hash_senha('senha123')}")
                    print(f"   Hash atual no banco:")
                    print(f"   {senha_hash_banco}")
                    
                    # Testa várias possibilidades
                    print(f"\n🧪 TESTES AUTOMÁTICOS:")
                    senhas_teste = ['senha123', 'Senha123', 'SENHA123', ' senha123', 'senha123 ']
                    for s_teste in senhas_teste:
                        if hash_senha(s_teste) == senha_hash_banco:
                            print(f"   ✅ MATCH ENCONTRADO COM: '{s_teste}'")
                            break
                    else:
                        print(f"   ❌ Nenhuma variação comum de 'senha123' deu match")
                    
                    ui.notification_show("❌ Senha incorreta!", type="error")
            
            except Exception as e:
                print(f"❌ Erro ao validar senha: {e}")
                import traceback
                traceback.print_exc()
                ui.notification_show("❌ Erro ao validar senha!", type="error")
            
            print("="*60 + "\n")
                        
        except Exception as e:
            print(f"\n❌ ERRO NO LOGIN: {str(e)}")
            import traceback
            traceback.print_exc()
            ui.notification_show(f"❌ Erro: {str(e)}", type="error")   


    # ============FUNÇÕES DE VALIDAR CNPJ/CPF===========
 
    def validar_cpf_completo(cpf):
        """Validação completa de CPF com dígitos verificadores"""
        cpf = ''.join(filter(str.isdigit, str(cpf)))

        if len(cpf) != 11:
            return False

        # Verifica se todos os dígitos são iguais
        if cpf == cpf[0] * 11:
            return False

        # Calcula primeiro dígito verificador
        soma = sum(int(cpf[i]) * (10 - i) for i in range(9))
        resto = soma % 11
        digito1 = 0 if resto < 2 else 11 - resto
        if int(cpf[9]) != digito1:
            return False

        # Calcula segundo dígito verificador
        soma = sum(int(cpf[i]) * (11 - i) for i in range(10))
        resto = soma % 11
        digito2 = 0 if resto < 2 else 11 - resto
        if int(cpf[10]) != digito2:
            return False

        return True

    def validar_cnpj_completo(cnpj):
        """Validação completa de CNPJ com dígitos verificadores"""
        cnpj = ''.join(filter(str.isdigit, str(cnpj)))

        if len(cnpj) != 14:
            return False

        # Verifica se todos os dígitos são iguais
        if cnpj == cnpj[0] * 14:
            return False

        # Calcula primeiro dígito verificador
        peso = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
        soma = sum(int(cnpj[i]) * peso[i] for i in range(12))
        resto = soma % 11
        digito1 = 0 if resto < 2 else 11 - resto
        if int(cnpj[12]) != digito1:
            return False

        # Calcula segundo dígito verificador
        peso = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
        soma = sum(int(cnpj[i]) * peso[i] for i in range(13))
        resto = soma % 11
        digito2 = 0 if resto < 2 else 11 - resto
        
        if int(cnpj[13]) != digito2:
            return False

        return True


    # ========== FUNÇÕES DE LIMPEZA DE FORMULÁRIOS ==========
    
    def limpar_form_procedimento():
        """Limpa o formulário de cadastro de procedimento"""
        try:
            ui.update_text("proc_nome", value="")
            ui.update_select("proc_grupo", selected="")
            ui.update_numeric("proc_preco", value=0)
            ui.update_text_area("proc_descricao", value="")
        except:
            pass
    
    def limpar_form_cliente():
        """Limpa o formulário de cadastro de cliente"""
        try:
            ui.update_text("cliente_nome", value="")
            ui.update_text("cliente_cpf", value="")
            ui.update_text("cliente_telefone", value="")
            ui.update_text("cliente_email", value="")
            ui.update_text("cliente_endereco", value="")
            ui.update_text("cliente_cidade", value="")
            ui.update_select("cliente_uf", selected="")
        except:
            pass
    
    def limpar_form_clinica():
        """Limpa o formulário de cadastro de clínica"""
        try:
            ui.update_text("cli_razao", value="")
            ui.update_text("cli_fantasia", value="")
            ui.update_text("cli_cnpj", value="")
            ui.update_text("cli_email", value="")
            ui.update_text("cli_telefone", value="")
            ui.update_text("cli_whatsapp", value="")
            ui.update_text("cli_cidade", value="")
            ui.update_select("cli_uf", selected="")
            ui.update_text("cli_endereco", value="")
            ui.update_text("cli_responsavel", value="")
            ui.update_text("cli_resp_contato", value="")
            ui.update_text("cli_senha", value="")
            ui.update_text("cli_banco", value="")
            ui.update_text("cli_agencia", value="")
            ui.update_text("cli_conta", value="")
            ui.update_text("cli_pix", value="")
            ui.update_text("cli_titular", value="")
            ui.update_select("cli_tipo_comissao", selected="percentual")
            ui.update_numeric("cli_comissao_perc", value=0)
            ui.update_numeric("cli_comissao_valor", value=0)
        except:
            pass
    
    def limpar_form_vendedor():
        """Limpa o formulário de cadastro de vendedor"""
        try:
            ui.update_text("vend_nome", value="")
            ui.update_text("vend_cpf", value="")
            ui.update_text("vend_telefone", value="")
            ui.update_text("vend_email", value="")
            ui.update_text("vend_endereco", value="")
            ui.update_numeric("vend_comissao_perc", value=0)
            ui.update_numeric("vend_comissao_valor", value=0)
        except:
            pass
    # =======================================================
    
    @reactive.Effect
    @reactive.event(input.btn_cadastrar_cliente)
    def cadastrar_cliente_auto():
        """Realiza o cadastro completo do cliente com validações"""
        try:
            print("\n" + "="*60)
            print("📝 CADASTRO DE CLIENTE - DEBUG")
            print("="*60)

            if not supabase: # Supondo que supabase está definido globalmente
                ui.notification_show("❌ Supabase não configurado", type="error")
                return

            # ========== 1. COLETA DADOS ==========
            nome = input.cadastro_nome().strip()
            cpf = input.cadastro_cpf().strip()
            email = input.cadastro_email().strip().lower()
            telefone = input.cadastro_telefone().strip()
            senha = input.cadastro_senha() # Senhas não precisam de strip()
            senha_confirma = input.cadastro_senha_confirma()
            pix_chave = input.cadastro_pix().strip()

            print(f"📋 Dados recebidos:")
            print(f"    Nome: {nome}")
            print(f"    CPF: {cpf}")
            print(f"    Email: {email}")
            print(f"    Telefone: {telefone}")
            print(f"    PIX: {pix_chave}") # Adicionado para debug

            # ========== 2. VALIDAÇÃO DE CAMPOS VAZIOS ==========
            campos_vazios = []
            if not nome: campos_vazios.append("Nome")
            if not cpf: campos_vazios.append("CPF")
            if not email: campos_vazios.append("Email")
            if not telefone: campos_vazios.append("Telefone")
            if not senha: campos_vazios.append("Senha")
            if not senha_confirma: campos_vazios.append("Confirmação de Senha")
            if not pix_chave: campos_vazios.append("Chave PIX")

            if campos_vazios: # Verifica se a lista não está vazia
                ui.notification_show(
                    f"⚠️ Preencha todos os campos obrigatórios!\n"
                    f"Faltam: {', '.join(campos_vazios)}",
                    type="warning",
                    duration=5
                )
                return

            # ========== 3. VALIDAÇÃO DE NOME ==========
            if len(nome) < 3:
                ui.notification_show("⚠️ Nome deve ter pelo menos 3 caracteres!", type="warning")
                return

            if not any(char.isalpha() for char in nome): # Garante que tenha pelo menos uma letra
                ui.notification_show("⚠️ Nome inválido! Deve conter letras.", type="warning")
                return
            print("✅ Nome válido") # Debug

            # ========== 4. VALIDAÇÃO DE EMAIL ==========
            import re # Importar no início do arquivo é melhor prática, mas ok aqui por simplicidade

            # Regex para validar email
            email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

            if not re.match(email_regex, email):
                ui.notification_show(
                    "⚠️ Email inválido!\n"
                    "Formato esperado: exemplo@dominio.com",
                    type="warning",
                    duration=5
                )
                return
            print(f"✅ Email válido: {email}")

            # ========== 5. VALIDAÇÃO DE SENHA ==========
            if len(senha) < 6:
                ui.notification_show(
                    "⚠️ A senha deve ter no mínimo 6 caracteres!",
                    type="warning"
                )
                return

            if len(senha) > 50: # Limite máximo razoável
                ui.notification_show(
                    "⚠️ A senha deve ter no máximo 50 caracteres!",
                    type="warning"
                )
                return

            # ========== 6. CONFIRMAÇÃO DE SENHA ==========
            if senha != senha_confirma:
                ui.notification_show(
                    "⚠️ As senhas não coincidem!\n"
                    "Digite a mesma senha nos dois campos.",
                    type="warning",
                    duration=5
                )
                return
            print(f"✅ Senhas conferem!")

            # Validação de força da senha (opcional mas recomendado)
            # Verifica se tem número OU maiúscula OU símbolo
            if not (any(char.isdigit() for char in senha) or \
                    any(char.isupper() for char in senha) or \
                    any(not char.isalnum() for char in senha)):
                if len(senha) < 8: # Só avisa se for curta E simples
                    ui.notification_show(
                        "⚠️ Senha fraca!\n"
                        "Recomendamos: mínimo 8 caracteres, com letras maiúsculas, minúsculas e números/símbolos.",
                        type="warning",
                        duration=6
                    )
                    # Não retorna, apenas avisa

            # ========== 7. VALIDAÇÃO DE CPF COMPLETA ==========
            cpf_limpo = limpar_documento(cpf) # Assume que limpar_documento remove não dígitos

            print(f"📄 CPF original: {cpf}")
            print(f"📄 CPF limpo: {cpf_limpo}")

            # Verifica se tem 11 dígitos
            if len(cpf_limpo) != 11:
                ui.notification_show(
                    f"⚠️ CPF inválido!\n"
                    f"O CPF deve ter 11 dígitos.\n"
                    f"Você digitou: {len(cpf_limpo)} dígitos",
                    type="warning",
                    duration=5
                )
                return

            # Verifica se todos os dígitos são iguais (CPF inválido)
            if cpf_limpo == cpf_limpo[0] * 11:
                ui.notification_show(
                    f"⚠️ CPF inválido!\n"
                    f"CPF não pode ter todos os dígitos iguais: {formatar_cpf(cpf_limpo)}", # Assume formatar_cpf
                    type="warning",
                    duration=5
                )
                return

            # VALIDAÇÃO DE DÍGITOS VERIFICADORES (Função interna para clareza)
            def validar_cpf_digitos(cpf_num):
                """Valida CPF com dígitos verificadores (recebe apenas números)"""
                if len(cpf_num) != 11: return False # Segurança extra
                # Calcula primeiro dígito verificador
                soma = sum(int(cpf_num[i]) * (10 - i) for i in range(9))
                resto = soma % 11
                digito1 = 0 if resto < 2 else 11 - resto

                if int(cpf_num[9]) != digito1:
                    return False

                # Calcula segundo dígito verificador
                soma = sum(int(cpf_num[i]) * (11 - i) for i in range(10))
                resto = soma % 11
                digito2 = 0 if resto < 2 else 11 - resto

                if int(cpf_num[10]) != digito2:
                    return False

                return True

            if not validar_cpf_digitos(cpf_limpo):
                ui.notification_show(
                    f"⚠️ CPF inválido!\n"
                    f"O CPF {formatar_cpf(cpf_limpo)} não passou na validação dos dígitos verificadores.\n" # Assume formatar_cpf
                    f"Verifique os números digitados.",
                    type="warning",
                    duration=6
                )
                return
            print(f"✅ CPF válido: {formatar_cpf(cpf_limpo)}") # Assume formatar_cpf

            # ========== 8. VALIDAÇÃO DE TELEFONE ==========
            telefone_limpo = ''.join(filter(str.isdigit, telefone))

            if not (10 <= len(telefone_limpo) <= 11): # Deve ter 10 (fixo+DDD) ou 11 (celular+DDD)
                ui.notification_show(
                    f"⚠️ Telefone inválido!\n"
                    f"Digite o telefone com DDD (10 ou 11 dígitos).\n"
                    f"Exemplo: (27) 99999-9999 ou (27) 3333-3333",
                    type="warning",
                    duration=5
                )
                return
            print(f"✅ Telefone válido: {formatar_whatsapp(telefone_limpo)}") # Assume formatar_whatsapp

            # ========== 9. VALIDAÇÃO DE PIX (Simples) ==========
            # Uma validação mais robusta exigiria verificar o tipo de chave
            if len(pix_chave) < 5 and '@' not in pix_chave: # Validação bem básica
                ui.notification_show(
                    "⚠️ Chave PIX parece inválida!\n"
                    "Digite uma chave válida (CPF, CNPJ, email, telefone ou aleatória)",
                    type="warning",
                    duration=5
                )
                return
            print("✅ Chave PIX (formato básico OK)") # Debug

            # ========== 10. VERIFICA DUPLICIDADE ==========
            print("\n🔍 Verificando duplicidades...")

            # Verifica CPF na tabela usuarios
            check_user_cpf = supabase.table('usuarios').select('id, nome').eq('cpf', cpf_limpo).execute()
            if check_user_cpf.data:
                nome_existente = check_user_cpf.data[0].get('nome', 'Não informado')
                ui.notification_show(
                    f"⚠️ Este CPF já está cadastrado como usuário!\n"
                    f"Nome: {nome_existente}\n"
                    f"Se é você, faça login.",
                    type="warning",
                    duration=6
                )
                return

            # Verifica CPF na tabela clientes
            check_cliente_cpf = supabase.table('clientes').select('id, nome_completo').eq('cpf', cpf_limpo).execute()
            if check_cliente_cpf.data:
                nome_existente = check_cliente_cpf.data[0].get('nome_completo', 'Não informado')
                ui.notification_show(
                    f"⚠️ Este CPF já está cadastrado como cliente!\n"
                    f"Nome: {nome_existente}\n"
                    f"Se é você, faça login.",
                    type="warning",
                    duration=6
                )
                return
            print(f"    ✅ CPF disponível")

            # Verifica email na tabela usuarios
            check_email = supabase.table('usuarios').select('id').eq('email', email).execute()
            if check_email.data:
                ui.notification_show(
                    f"⚠️ Este email já está cadastrado!\n"
                    f"Email: {email}\n"
                    f"Use outro email ou faça login.",
                    type="warning",
                    duration=6
                )
                return
            print(f"    ✅ Email disponível")

            print("\n✅ Todas validações OK! Iniciando criação...")

            # ========== 11. GERA CÓDIGO DO CLIENTE ==========
            codigo_cliente = gerar_codigo_cliente() # Assume que gerar_codigo_cliente exista
            print(f"🆔 Código do Cliente gerado: {codigo_cliente}")

            # ========== 12. CRIA USUÁRIO ==========
            # Importar uuid no início do arquivo é melhor prática
            import uuid
            usuario_id = str(uuid.uuid4())
            # senha_limpa = senha.strip() # Senha já está sem espaços extras do input
            senha_hash = hash_senha(senha) # Assume que hash_senha exista

            usuario_data = {
                "id": usuario_id,
                "nome": nome,
                "email": email,
                "cpf": cpf_limpo,
                "senha_hash": senha_hash,
                "telefone": telefone_limpo,
                "tipo_usuario": "cliente", # Define como cliente
                "pix_chave": pix_chave,
                "ativo": True # Define como ativo por padrão
            }

            print("💾 Inserindo usuário no banco...")
            usuario_result = supabase.table('usuarios').insert(usuario_data).execute()

            # Verifica se a inserção do usuário falhou
            # A API do Supabase retorna erro em 'error', não apenas dados vazios
            if hasattr(usuario_result, 'error') and usuario_result.error:
                 print(f"❌ Erro Supabase ao criar usuário: {usuario_result.error}")
                 ui.notification_show(f"❌ Erro ao criar usuário: {usuario_result.error.message}", type="error")
                 return
            elif not usuario_result.data: # Fallback caso a API mude
                 print(f"❌ Erro desconhecido ao criar usuário (sem dados retornados). Resposta: {usuario_result}")
                 ui.notification_show("❌ Erro desconhecido ao criar usuário!", type="error")
                 return

            print("✅ Usuário criado!")

            # ========== 13. CRIA CLIENTE ==========
            cliente_data = {
                "nome_completo": nome,
                "cpf": cpf_limpo,
                "codigo": codigo_cliente,
                "telefone": telefone_limpo,
                "email": email,
                "usuario_id": usuario_id, # Vincula ao usuário criado
                "ativo": True
            }

            print("💾 Inserindo cliente no banco...")
            cliente_result = supabase.table('clientes').insert(cliente_data).execute()

            # Verifica se a inserção do cliente falhou e faz Rollback do usuário
            if hasattr(cliente_result, 'error') and cliente_result.error:
                print(f"❌ Erro Supabase ao criar cliente: {cliente_result.error}")
                print(f"⚠️ ROLLBACK: Removendo usuário {usuario_id}...")
                supabase.table('usuarios').delete().eq('id', usuario_id).execute() # Tenta  o usuário
                ui.notification_show(f"❌ Erro ao cadastrar cliente: {cliente_result.error.message}", type="error")
                return
            elif not cliente_result.data: # Fallback
                print(f"❌ Erro desconhecido ao criar cliente (sem dados retornados). Resposta: {cliente_result}")
                print(f"⚠️ ROLLBACK: Removendo usuário {usuario_id}...")
                supabase.table('usuarios').delete().eq('id', usuario_id).execute() # Tenta  o usuário
                ui.notification_show("❌ Erro desconhecido ao cadastrar cliente!", type="error")
                return

            print("✅ Cliente criado!")
            print("\n📧 Enviando email de boas-vindas...")
            enviar_email_boas_vindas_cliente(nome, email, codigo_cliente)
            print("="*60 + "\n")

            # ========== 14. NOTIFICAÇÃO DE SUCESSO ==========
            ui.notification_show(
                f"✅ Cadastro realizado com sucesso!\n\n"
                f"🔐 Agora é só fazer login com seu CPF e senha!"
                f"📬 Enviamos um email de boas-vindas!\n"
                f"⚠️ Verifique sua caixa de SPAM/LIXO ELETRÔNICO\n\n",                
                type="message",
                duration=20  # Duração aumentada para ler tudo
            )

            # ========== 15. LIMPA FORMULÁRIO ==========
            ui.update_text("cadastro_nome", value="")
            ui.update_text("cadastro_cpf", value="")
            ui.update_text("cadastro_email", value="")
            ui.update_text("cadastro_telefone", value="")
            ui.update_text("cadastro_senha", value="")  # ✅ CORRETO
            ui.update_text("cadastro_senha_confirma", value="")  # ✅ CORRETO
            ui.update_text("cadastro_pix", value="")

        # Captura exceções gerais durante todo o processo
        except Exception as e:
            print(f"\n❌ ERRO CRÍTICO no cadastro: {e}")
            import traceback
            traceback.print_exc()
            print("="*60 + "\n")
            ui.notification_show(
                f"❌ Erro inesperado ao cadastrar: {str(e)}\n"
                f"Tente novamente ou contate o suporte.",
                type="error",
                duration=8
            )

    @reactive.Effect
    @reactive.event(input.btn_cadastrar_clinica_auto)
    def cadastrar_clinica_auto():
        """Cadastro de clínica pelo próprio usuário (CORRIGIDO)"""
        try:
            print("\n" + "="*60)
            print("🏥 AUTO-CADASTRO DE CLÍNICA - DEBUG")
            print("="*60)

            if not supabase:
                ui.notification_show("❌ Supabase não configurado", type="error")
                return

            # ========== COLETA DADOS (IDs CORRIGIDOS) ==========
            razao = input.cadastro_razao_social().strip()         # CORRIGIDO
            fantasia = input.cadastro_nome_fantasia().strip()     # CORRIGIDO e adicionado
            cnpj = input.cadastro_cnpj().strip()                  # CORRIGIDO
            telefone = input.cadastro_telefone_clinica().strip()  # CORRIGIDO
            whatsapp = input.cadastro_whatsapp_clinica().strip()  # CORRIGIDO
            email = input.cadastro_email_clinica().strip().lower()# CORRIGIDO
            endereco = input.cadastro_endereco().strip()          # CORRIGIDO
            cidade = input.cadastro_cidade().strip()              # CORRIGIDO
            uf = input.cadastro_uf()                              # CORRIGIDO
            # --- VERIFIQUE ESTES IDs NA SUA UI ---
            responsavel = input.cadastro_responsavel().strip() # ASSUMINDO ID="cadastro_responsavel" na UI
            resp_contato = input.cadastro_resp_contato().strip() # ASSUMINDO ID="cadastro_resp_contato" na UI
            # -------------------------------------
            senha = input.cadastro_senha_clinica()                # CORRIGIDO
            # --- ADICIONE ESTE INPUT NA UI ---
            senha_confirma = input.cadastro_senha_confirma_clinica() # NOVO - ID="cadastro_senha_confirma_clinica"
            # ---------------------------------
            pix_chave = input.cadastro_pix_chave().strip()        # CORRIGIDO
            pix_tipo = input.cadastro_pix_tipo()                  # CORRIGIDO

            print(f"📋 Dados recebidos:")
            print(f"    Razão Social: {razao}")
            print(f"    Nome Fantasia: {fantasia}") # Adicionado para debug
            print(f"    CNPJ: {cnpj}")
            # Adicione mais prints se necessário

            # ========== VALIDAÇÕES ==========
            campos_vazios = []
            if not razao: campos_vazios.append("Razão Social")
            if not cnpj: campos_vazios.append("CNPJ")
            # Telefone não é mais obrigatório na UI, mas vamos manter a validação se preenchido
            # if not telefone: campos_vazios.append("Telefone")
            if not whatsapp: campos_vazios.append("WhatsApp") # WhatsApp é obrigatório na UI
            if not email: campos_vazios.append("Email")
            # Endereço não é mais obrigatório na UI
            # if not endereco: campos_vazios.append("Endereço")
            if not endereco: campos_vazios.append("Endereço Completo")
            if not cidade: campos_vazios.append("Cidade")
            if not uf: campos_vazios.append("UF")
            # --- VERIFIQUE SE RESPONSAVEL É OBRIGATÓRIO NA UI ---
            # if not responsavel: campos_vazios.append("Nome do Responsável")
            # if not resp_contato: campos_vazios.append("Contato do Responsável")
            # ----------------------------------------------------
            if not senha: campos_vazios.append("Senha")
            if not senha_confirma: campos_vazios.append("Confirmação de Senha") # Adicionado
            if not pix_chave: campos_vazios.append("Chave PIX")
            if not pix_tipo: campos_vazios.append("Tipo de Chave PIX") # Adicionado

            # ========== VALIDAÇÃO DOS TERMOS ==========
            print("\n🔍 Verificando termos...")

            termos_nao_aceitos = []
            if not input.termo_comissao():
                termos_nao_aceitos.append("Comissão de 12%")
            if not input.termo_parcelas():
                termos_nao_aceitos.append("Parcelas de pagamento")
            if not input.termo_atendimento():
                termos_nao_aceitos.append("Controle via app")
            if not input.termo_procedimentos():
                termos_nao_aceitos.append("Cadastro de procedimentos")

            if termos_nao_aceitos:
                ui.notification_show(
                    f"⚠️ Você precisa aceitar todos os termos!\n\n"
                    f"Marque:\n" + "\n".join([f"• {t}" for t in termos_nao_aceitos]),
                    type="warning",
                    duration=8
                )
                return

            print("✅ Todos os termos aceitos")

            if campos_vazios:
                ui.notification_show(
                    f"⚠️ Preencha todos os campos obrigatórios!\n"
                    f"Faltam: {', '.join(campos_vazios)}",
                    type="warning",
                    duration=5
                )
                return

            # Valida CNPJ
            cnpj_limpo = limpar_documento(cnpj)

            if len(cnpj_limpo) != 14:
                ui.notification_show(
                    f"⚠️ CNPJ inválido!\n"
                    f"O CNPJ deve ter 14 dígitos.\n"
                    f"Você digitou: {len(cnpj_limpo)} dígitos",
                    type="warning",
                    duration=5
                )
                return

            if not validar_cnpj_completo(cnpj_limpo): # Assume que validar_cnpj_completo existe
                ui.notification_show(
                    f"⚠️ CNPJ inválido!\n"
                    f"O CNPJ {formatar_cnpj(cnpj_limpo)} não passou na validação.\n" # Assume formatar_cnpj
                    f"Verifique os números digitados.",
                    type="warning",
                    duration=6
                )
                return

            print(f"✅ CNPJ válido: {formatar_cnpj(cnpj_limpo)}")

            # Valida Email
            import re
            email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_regex, email):
                ui.notification_show(
                    "⚠️ Email inválido!\n"
                    "Formato esperado: exemplo@dominio.com",
                    type="warning",
                    duration=5
                )
                return

            # Valida Senha
            if len(senha) < 6:
                ui.notification_show(
                    "⚠️ A senha deve ter no mínimo 6 caracteres!",
                    type="warning"
                )
                return

            if senha != senha_confirma: # Adicionado validação de confirmação
                ui.notification_show(
                    "⚠️ As senhas não coincidem!\n"
                    "Digite a mesma senha nos dois campos.",
                    type="warning",
                    duration=5
                )
                return

            print(f"✅ Senhas conferem!")

            # Valida Telefones (WhatsApp é obrigatório, Telefone opcional)
            telefone_limpo = ''.join(filter(str.isdigit, telefone)) if telefone else ''
            whatsapp_limpo = ''.join(filter(str.isdigit, whatsapp))

            if telefone and not (10 <= len(telefone_limpo) <= 11): # Valida telefone só se preenchido
                ui.notification_show(
                    "⚠️ Telefone inválido!\n"
                    "Digite com DDD (10 ou 11 dígitos).",
                    type="warning"
                )
                return

            if not (10 <= len(whatsapp_limpo) <= 11): # WhatsApp é obrigatório
                ui.notification_show(
                    "⚠️ WhatsApp inválido!\n"
                    "Digite com DDD (10 ou 11 dígitos).",
                    type="warning"
                )
                return

            # ========== VERIFICA DUPLICIDADE ==========
            print("\n🔍 Verificando duplicidades...")

            # Verifica CNPJ como 'cpf' na tabela usuarios (como era antes)
            check_user = supabase.table('usuarios').select('id, nome').eq('cpf', cnpj_limpo).execute()
            if check_user.data:
                nome_existente = check_user.data[0].get('nome', 'Não informado')
                ui.notification_show(
                    f"⚠️ Este CNPJ já está cadastrado como usuário!\n"
                    f"Nome: {nome_existente}\n"
                    f"Se é sua clínica, faça login.",
                    type="warning",
                    duration=6
                )
                return

            # Verifica CNPJ na tabela clinicas
            check_clinica = supabase.table('clinicas').select('id, razao_social').eq('cnpj', cnpj_limpo).execute()
            if check_clinica.data:
                nome_existente = check_clinica.data[0].get('razao_social', 'Não informado')
                ui.notification_show(
                    f"⚠️ Este CNPJ já está cadastrado como clínica!\n"
                    f"Nome: {nome_existente}\n"
                    f"Se é sua clínica, faça login.",
                    type="warning",
                    duration=6
                )
                return

            print(f"    ✅ CNPJ disponível")

            # Verifica Email na tabela usuarios
            check_email_user = supabase.table('usuarios').select('id').eq('email', email).execute()
            if check_email_user.data:
                ui.notification_show(
                    f"⚠️ Este Email já está cadastrado para outro usuário!\n"
                    f"Email: {email}\n"
                    f"Use outro email ou faça login.",
                    type="warning",
                    duration=6
                )
                return

            # Verifica Email na tabela clinicas (redundante se email do usuário for único, mas seguro)
            check_email_clinica = supabase.table('clinicas').select('id').eq('email', email).execute()
            if check_email_clinica.data:
                 ui.notification_show(
                    f"⚠️ Este Email já está cadastrado para outra clínica!\n"
                    f"Email: {email}\n"
                    f"Use outro email.",
                    type="warning",
                    duration=6
                )
                 return

            print(f"    ✅ Email disponível")

            print("\n✅ Todas validações OK! Iniciando criação...")

            # ========== CRIA USUÁRIO ==========
            import uuid
            usuario_id = str(uuid.uuid4())
            senha_hash = hash_senha(senha.strip()) # Assume hash_senha existe

            usuario_data = {
                "id": usuario_id,
                "nome": razao, # Usa Razão Social como nome do usuário
                "email": email,
                "cpf": cnpj_limpo, # Salva CNPJ no campo cpf da tabela usuarios
                "senha_hash": senha_hash,
                "telefone": whatsapp_limpo, # Salva WhatsApp como telefone principal do usuário
                "tipo_usuario": "clinica",
                "ativo": True
            }

            print("💾 Inserindo usuário no banco...")
            usuario_result = supabase.table('usuarios').insert(usuario_data).execute()

            if hasattr(usuario_result, 'error') and usuario_result.error:
                print(f"❌ Erro Supabase ao criar usuário: {usuario_result.error}")
                ui.notification_show(f"❌ Erro ao criar usuário: {usuario_result.error.message}", type="error")
                return
            elif not usuario_result.data: # Fallback
                print(f"❌ Erro desconhecido ao criar usuário (sem dados retornados). Resposta: {usuario_result}")
                ui.notification_show("❌ Erro desconhecido ao criar usuário!", type="error")
                return

            print("✅ Usuário criado!")

            # ========== CRIA CLÍNICA ==========
            dados_pix = {
                "chave": pix_chave,
                "tipo": pix_tipo
            }

            clinica_data = {
                "usuario_id": usuario_id,
                "razao_social": razao,
                "nome_fantasia": fantasia or None, # Usa a variável 'fantasia' lida no início
                "cnpj": cnpj_limpo,
                "email": email,
                "telefone": telefone_limpo or None, # Telefone opcional
                "whatsapp": whatsapp_limpo, # WhatsApp obrigatório
                "endereco_rua": endereco or None, # Endereço opcional
                "endereco_cidade": cidade,
                "endereco_estado": uf,
                "responsavel_nome": responsavel or None, # Responsável opcional
                "responsavel_contato": resp_contato or None, # Contato opcional
                "dados_pix": json.dumps(dados_pix), # Garante que dados_pix seja JSON
                "ativo": True
                # vendedor_id: None (removido, pois é auto-cadastro)
            }

            print("💾 Inserindo clínica no banco...")
            clinica_result = supabase.table('clinicas').insert(clinica_data).execute()

            # Verifica erro e faz Rollback do usuário se necessário
            if hasattr(clinica_result, 'error') and clinica_result.error:
                print(f"❌ Erro Supabase ao criar clínica: {clinica_result.error}")
                print(f"⚠️ ROLLBACK: Removendo usuário {usuario_id}...")
                supabase.table('usuarios').delete().eq('id', usuario_id).execute() # Tenta remover usuário
                ui.notification_show(f"❌ Erro ao cadastrar clínica: {clinica_result.error.message}", type="error")
                return
            elif not clinica_result.data: # Fallback
                print(f"❌ Erro desconhecido ao criar clínica (sem dados retornados). Resposta: {clinica_result}")
                print(f"⚠️ ROLLBACK: Removendo usuário {usuario_id}...")
                supabase.table('usuarios').delete().eq('id', usuario_id).execute() # Tenta remover usuário
                ui.notification_show("❌ Erro desconhecido ao cadastrar clínica!", type="error")
                return
           
            print("✅ Clínica criada!")
            
            clinica_id = clinica_result.data[0]['id']
            
            # ========== CRIAR COMISSÃO PADRÃO 12% ==========
            try:
                comissao_data = {
                    "clinica_id": clinica_id,
                    "tipo": "percentual",
                    "valor_percentual": 12
                }
                
                print(f"\n{'='*60}")
                print(f"💼 CRIANDO COMISSÃO PARA CLÍNICA")
                print(f"{'='*60}")
                print(f"Clínica ID: {clinica_id}")
                print(f"Clínica: {fantasia}")
                print(f"Tipo: percentual")
                print(f"Percentual: 12%")
                
                comissao_result = supabase.table('comissoes_clinica').insert(comissao_data).execute()
                
                if comissao_result.data:
                    print(f"✅ Comissão criada com sucesso!")
                    print(f"Comissão ID: {comissao_result.data[0].get('id')}")
                else:
                    print(f"⚠️ Comissão não retornou dados, mas pode ter sido criada")
                
                print(f"{'='*60}\n")
                
            except Exception as e:
                print(f"\n{'='*60}")
                print(f"❌ ERRO AO CRIAR COMISSÃO!")
                print(f"{'='*60}")
                print(f"Erro: {e}")
                import traceback
                traceback.print_exc()
                print(f"{'='*60}\n")
                
                # Não interrompe o cadastro, mas avisa
                print("⚠️ Clínica cadastrada sem comissão. Configure manualmente.")

            # ========== GEOCODING AUTOMÁTICO ==========
            print("\n🌍 Obtendo coordenadas GPS do endereço...")

            # Pega endereço do input
            endereco_input = input.cadastro_endereco()  # Ex: "Rua Sete de Setembro, 500"

            # Chama geocoding
            lat, lon = obter_coordenadas_por_endereco(endereco_input, cidade, uf)

            if lat and lon:
                # Atualiza coordenadas no banco
                try:
                    supabase.table('clinicas').update({
                        'latitude': lat,
                        'longitude': lon
                    }).eq('cnpj', cnpj_limpo).execute()
                    
                    print(f"✅ GPS cadastrado: {lat}, {lon}")
                    ui.notification_show(
                        f"📍 GPS Cadastrado!\n"
                        f"Lat: {lat:.4f}, Lon: {lon:.4f}",
                        type="message",
                        duration=5
                    )
                except Exception as e:
                    print(f"⚠️ Erro ao salvar GPS: {e}")
            else:
                print(f"⚠️ Não foi possível obter GPS. Você pode atualizar manualmente depois.")
                ui.notification_show(
                    f"⚠️ Não conseguimos localizar o endereço automaticamente.\n"
                    f"A clínica foi cadastrada, mas sem GPS.",
                    type="warning",
                    duration=8
                )


            # ========== ENVIAR EMAIL DE BOAS-VINDAS ==========
            print("\n📧 Enviando email de instruções...")
            enviar_email_boas_vindas_clinica(razao, email)

            print("="*60 + "\n")
            
            
            # ========== NOTIFICAÇÃO DE SUCESSO ==========
            # Mensagem de GPS
            gps_msg = ""
            if lat and lon:
                gps_msg = f"📍 GPS: {lat:.4f}, {lon:.4f}\n"
            else:
                gps_msg = f"⚠️ GPS não cadastrado (endereço não localizado)\n"

            ui.notification_show(
                f"✅ Cadastro realizado com sucesso!\n\n"
                f"🏥 Clínica: {razao}\n"
                f"📧 Email: {email}\n"
                f"{gps_msg}\n"
                f"🔐 Faça login com o CNPJ e senha cadastrados!\n"
                f"📬 Enviamos um email com instruções de uso!\n"
                f"⚠️ Verifique sua caixa de SPAM/LIXO ELETRÔNICO",
                type="message",
                duration=15
            )
            

            # ========== LIMPA FORMULÁRIO (IDs CORRIGIDOS) ==========
            ui.update_text("cadastro_razao_social", value="")      # CORRIGIDO
            ui.update_text("cadastro_nome_fantasia", value="")    # CORRIGIDO
            ui.update_text("cadastro_cnpj", value="")             # CORRIGIDO
            ui.update_text("cadastro_telefone_clinica", value="") # CORRIGIDO
            ui.update_text("cadastro_whatsapp_clinica", value="") # CORRIGIDO
            ui.update_text("cadastro_email_clinica", value="")    # CORRIGIDO
            ui.update_text("cadastro_endereco", value="")         # CORRIGIDO
            ui.update_text("cadastro_cidade", value="")           # CORRIGIDO
            ui.update_select("cadastro_uf", selected="")          # CORRIGIDO
            ui.update_text("cadastro_responsavel", value="")      # VERIFICAR ID NA UI
            ui.update_text("cadastro_resp_contato", value="")     # VERIFICAR ID NA UI
            ui.update_text("cadastro_senha_clinica", value="")    # CORRIGIDO
            ui.update_text("cadastro_senha_confirma_clinica", value="") # NOVO
            ui.update_text("cadastro_pix_chave", value="")        # CORRIGIDO
            ui.update_select("cadastro_pix_tipo", selected="")    # CORRIGIDO (ou valor default)


        except Exception as e:
            print(f"\n❌ ERRO CRÍTICO no cadastro da clínica: {e}")
            import traceback
            traceback.print_exc()
            print("="*60 + "\n")
            ui.notification_show(
                f"❌ Erro inesperado ao cadastrar: {str(e)}\n"
                f"Tente novamente ou contate o suporte.",
                type="error",
                duration=8
            )

    @reactive.effect
    @reactive.event(input.btn_ir_cadastro_cliente)
    def ir_para_cadastro_cliente():
        """Navega para tela de cadastro de cliente"""
        tela_atual.set("cadastro_cliente")

    @reactive.effect
    @reactive.event(input.btn_ir_cadastro_clinica)
    def ir_para_cadastro_clinica():
        """Navega para tela de cadastro de clínica"""
        tela_atual.set("cadastro_clinica")

    @reactive.effect
    @reactive.event(input.btn_voltar_login)
    def voltar_para_login():
        """Volta para tela de login"""
        tela_atual.set("login")

    @output
    @render.ui
    def tela_login_cadastro():
        """Renderiza a tela atual: login, cadastro_cliente ou cadastro_clinica"""
        tela = tela_atual()
        
        # ========== TELA 1: LOGIN ==========
        if tela == "login":
            return ui.div(
                {"class": "card-custom"},
                
                # LOGO NO TOPO DO CARD
                ui.div(
                    {"style": "text-align: center; margin-bottom: 2rem; padding-bottom: 2rem; border-bottom: 2px solid #E0F2F1;"},
                    ui.img(src="https://github.com/AMalta/MedPIX/blob/0e7c9ede0d9f51ca7e552b59e999047894baae79/images/logoMP.jpeg", 
                           style="height: 140px; width: auto; display: inline-block;")
                ),
                
                ui.h3("🔐 Fazer Login", style="text-align: center; margin-bottom: 2rem;"),
                
                ui.div(
                    ui.tags.label("CPF ou CNPJ", style="font-weight: 600; margin-bottom: 0.5rem; display: block;"),
                    ui.input_text("login_documento", "", 
                                 placeholder="000.000.000-00 ou 00.000.000/0000-00"),
                    ui.div(
                        {"style": "font-size: 0.8rem; color: #546E7A; margin-top: 0.25rem;"},
                        "💡 Digite apenas os números"
                    )
                ),
                
                ui.input_password("login_senha", "Senha", placeholder="********"),
                
                ui.input_action_button("btn_login", "Entrar", 
                                      class_="btn-primary w-100 mt-3"),
                
                ui.hr(style="margin: 2rem 0;"),
                
                ui.h5("📝 Ainda não tem conta?", style="text-align: center; margin-bottom: 1rem;"),
                
                ui.row(
                    ui.column(6,
                        ui.input_action_button("btn_ir_cadastro_cliente", 
                                              "👤 Sou Cliente", 
                                              class_="btn-success w-100",
                                              style="padding: 1rem;")
                    ),
                    ui.column(6,
                        ui.input_action_button("btn_ir_cadastro_clinica", 
                                              "🏥 Sou Clínica", 
                                              class_="btn-info w-100",
                                              style="padding: 1rem;")
                    )
                )
                
            )
        
        # ========== TELA 2: CADASTRO CLIENTE ==========
        elif tela == "cadastro_cliente":
            return ui.div(
                {"class": "card-custom"},
                
                ui.input_action_button("btn_voltar_login", "← Voltar", 
                                      class_="btn-outline-secondary mb-3"),
                
                ui.h3("📝 Cadastro de Cliente", style="text-align: center; margin-bottom: 2rem;"),
                
                # VANTAGENS PARA CLIENTES
                ui.div(
                    {"class": "card-custom", "style": "background: linear-gradient(135deg, #1DD1A1, #0D9488); color: white; margin-bottom: 2rem;"},
                    ui.h4("🎁 Vantagens Exclusivas para Você!", style="text-align: center; color: white; margin-bottom: 1.5rem;"),
                    ui.row(
                        ui.column(6,
                            ui.div(
                                {"style": "text-align: center; padding: 1rem;"},
                                ui.div("💰", style="font-size: 3rem;"),
                                ui.h6("Cashback Progressivo", style="color: white; margin-top: 1rem;"),
                                ui.p("Comece como bronze e siga para diamante!", style="color: white; opacity: 0.9; font-size: 0.9rem;")
                            )
                        ),
                        ui.column(6,
                            ui.div(
                                {"style": "text-align: center; padding: 1rem;"},
                                ui.div("⏰", style="font-size: 3rem;"),
                                ui.h6("Sem Pressão", style="color: white; margin-top: 1rem;"),
                                ui.p("30 dias para agendar!", style="color: white; opacity: 0.9; font-size: 0.9rem;")
                            )
                        )
                    )
                ),
                
                # FORMULÁRIO
                ui.input_text("cadastro_nome", "Nome Completo*", placeholder="Seu nome completo"),
                
                ui.input_text("cadastro_cpf", "CPF*", placeholder="000.000.000-00"),
                ui.tags.small("💡 Apenas números. Será validado.", 
                             style="color: #546E7A; font-size: 0.8rem; display: block; margin-top: -0.5rem; margin-bottom: 1rem;"),
                
                ui.input_text("cadastro_email", "Email*", placeholder="seu@email.com"),
                ui.tags.small("📧 Use um email válido e que você acessa.", 
                             style="color: #546E7A; font-size: 0.8rem; display: block; margin-top: -0.5rem; margin-bottom: 1rem;"),
                
                ui.input_text("cadastro_telefone", "WhatsApp*", placeholder="(27) 99999-9999"),
                
                ui.input_password("cadastro_senha", "Senha*", placeholder="Mínimo 6 caracteres"),
                ui.tags.small("🔐 Dica: Use letras, números e seja criativo!", 
                             style="color: #546E7A; font-size: 0.8rem; display: block; margin-top: -0.5rem; margin-bottom: 1rem;"),
                ui.input_password("cadastro_senha_confirma", "Confirmar Senha*", placeholder="Digite a senha novamente"),
                
                ui.input_text("cadastro_pix", "Chave PIX para Receber Cashback*", 
                             placeholder="CPF, Email, Telefone ou Chave Aleatória"),
                ui.tags.small("💰 Você receberá seu cashback nesta chave", 
                             style="color: #10b981; font-size: 0.8rem; display: block; margin-top: -0.5rem; margin-bottom: 1rem;"),
                
                ui.input_action_button("btn_cadastrar_cliente", "✅ Cadastrar", 
                                      class_="btn-primary w-100 mt-3",
                                      style="padding: 1rem; font-size: 1.1rem; font-weight: 600;")
            )
        
        # ========== TELA 3: CADASTRO CLÍNICA ==========
        elif tela == "cadastro_clinica":
            return ui.div(
                {"class": "card-custom"},
                
                ui.input_action_button("btn_voltar_login", "← Voltar", 
                                      class_="btn-outline-secondary mb-3"),
                
                ui.h3("🏥 Cadastro de Clínica", style="text-align: center; margin-bottom: 2rem;"),
                
                # VANTAGENS PARA CLÍNICAS
                ui.div(
                    {"class": "card-custom", "style": "background: linear-gradient(135deg, #f093fb, #f5576c); color: white; margin-bottom: 2rem;"},
                    ui.h4("💼 Benefícios para sua Clínica!", style="text-align: center; color: white; margin-bottom: 1.5rem;"),
                    ui.row(
                        ui.column(4,
                            ui.div(
                                {"style": "text-align: center; padding: 1rem;"},
                                ui.div("📈", style="font-size: 3rem;"),
                                ui.h6("Mais Clientes", style="color: white; margin-top: 1rem;"),
                                ui.p("Aumente sua carteira", style="color: white; opacity: 0.9; font-size: 0.85rem;")
                            )
                        ),
                        ui.column(4,
                            ui.div(
                                {"style": "text-align: center; padding: 1rem;"},
                                ui.div("💳", style="font-size: 3rem;"),
                                ui.h6("Receba Rápido", style="color: white; margin-top: 1rem;"),
                                ui.p("Recebimento antecipado", style="color: white; opacity: 0.9; font-size: 0.85rem;")
                            )
                        ),
                        ui.column(4,
                            ui.div(
                                {"style": "text-align: center; padding: 1rem;"},
                                ui.div("📊", style="font-size: 3rem;"),
                                ui.h6("Gestão Fácil", style="color: white; margin-top: 1rem;"),
                                ui.p("Controle total online", style="color: white; opacity: 0.9; font-size: 0.85rem;")
                            )
                        )
                    )
                ),
                
                # FORMULÁRIO
                ui.row(
                    ui.column(12, ui.input_text("cadastro_razao_social", "Razão Social*", placeholder="Nome oficial da empresa"))
                ),
                ui.row(
                    ui.column(12, ui.input_text("cadastro_nome_fantasia", "Nome Fantasia", placeholder="Nome comercial"))
                ),
                
                ui.input_text("cadastro_cnpj", "CNPJ*", placeholder="00.000.000/0000-00"),
                ui.tags.small("🏢 Apenas números. Será validado.", 
                             style="color: #546E7A; font-size: 0.8rem; display: block; margin-top: -0.5rem; margin-bottom: 1rem;"),
                
                ui.row(
                    ui.column(6, ui.input_text("cadastro_email_clinica", "Email*", placeholder="contato@clinica.com")),
                    ui.column(6, ui.input_text("cadastro_telefone_clinica", "Telefone", placeholder="(27) 3333-4444"))
                ),
                
                ui.input_text("cadastro_whatsapp_clinica", "WhatsApp*", placeholder="(27) 99999-9999"),
                ui.tags.small("📱 Principal número para contato", 
                             style="color: #546E7A; font-size: 0.8rem; display: block; margin-top: -0.5rem; margin-bottom: 1rem;"),
                
                ui.row(
                    ui.column(8, ui.input_text("cadastro_cidade", "Cidade*", placeholder="Ex: Vitória")),
                    ui.column(4, ui.input_select("cadastro_uf", "UF*", 
                        choices={"": "Selecione", "AC": "AC", "AL": "AL", "AP": "AP", "AM": "AM", 
                                 "BA": "BA", "CE": "CE", "DF": "DF", "ES": "ES", "GO": "GO", 
                                 "MA": "MA", "MT": "MT", "MS": "MS", "MG": "MG", "PA": "PA", 
                                 "PB": "PB", "PR": "PR", "PE": "PE", "PI": "PI", "RJ": "RJ", 
                                 "RN": "RN", "RS": "RS", "RO": "RO", "RR": "RR", "SC": "SC", 
                                 "SP": "SP", "SE": "SE", "TO": "TO"}))
                ),
                
                ui.input_text("cadastro_endereco", "Endereço Completo*", placeholder="Rua Nome da Silva, 123, Centro"),
                ui.tags.small("📍 Será usado para calcular distâncias. Seja o mais específico possível.", 
             style="color: #1DD1A1; font-size: 0.8rem; display: block; margin-top: -0.5rem; margin-bottom: 1rem;"),
                ui.h5("👤 Responsável pela Clínica (Opcional)"), # Section title
                ui.row(
                    # --- ADD THESE LINES ---
                    ui.column(6, ui.input_text("cadastro_responsavel", "Nome do Responsável", placeholder="Nome de quem responde pela clínica")),
                    ui.column(6, ui.input_text("cadastro_resp_contato", "Contato do Responsável", placeholder="Telefone ou email do responsável"))
                    # ---------------------
                ),
                
                ui.hr(),
                
                ui.h5("🔑 Senha de Acesso"),
                ui.p("Você fará login usando o CNPJ cadastrado acima", 
                     style="color: #546E7A; font-size: 0.9rem; margin-bottom: 1rem;"),
                ui.input_password("cadastro_senha_clinica", "Senha*", placeholder="Mínimo 6 caracteres"),
                ui.input_password("cadastro_senha_confirma_clinica", "Confirmar Senha*", placeholder="Digite a senha novamente"),
                
                ui.hr(),
                
                ui.h5("💳 Dados para Recebimento"),
                ui.div(
                    {"class": "card-custom", "style": "background: #dcfce7; padding: 1rem; margin-bottom: 1rem;"},
                    ui.row(
                        ui.column(6,
                            ui.input_text("cadastro_pix_chave", "Chave PIX*", 
                                         placeholder="CPF/CNPJ, Email, Telefone ou Aleatória")
                        ),
                        ui.column(6,
                            ui.input_select("cadastro_pix_tipo", "Tipo de Chave*",
                                choices={
                                    "": "Selecione",
                                    "cpf": "CPF",
                                    "cnpj": "CNPJ",
                                    "email": "Email",
                                    "telefone": "Telefone",
                                    "aleatoria": "Aleatória"
                                })
                        )
                    ),
                    ui.tags.small("💰 Você receberá os pagamentos nesta chave",
                                 style="color: #15803d; font-size: 0.85rem;")
                ),
                
                ui.hr(),

                # TERMOS E CIÊNCIA
                ui.h5("📋 Termos de Uso", style="margin-top: 1.5rem;"),
                ui.div(
                    {"class": "card-custom", "style": "background: #fef3c7; padding: 1.5rem; border: 2px solid #f59e0b;"},
                    ui.p("Leia atentamente e marque todas as opções abaixo:", 
                         style="margin: 0 0 1rem 0; font-weight: 600; color: #92400e;"),
                    
                    ui.input_checkbox("termo_comissao", 
                        ui.HTML("<span style='color: #78350f;'>Estou ciente de que a <strong>comissão do MedPIX é de 12%</strong> sobre cada venda</span>"),
                        value=False),
                    
                    ui.input_checkbox("termo_parcelas", 
                        ui.HTML("<span style='color: #78350f;'>Estou ciente de que o pagamento será dividido em <strong>2 parcelas</strong>: <br>• <strong>Parcela 1 (50%)</strong>: Paga antecipadamente após confirmação do pagamento<br>• <strong>Parcela 2 (50%)</strong>: Paga após finalização dos atendimentos</span>"),
                        value=False),
                    
                    ui.input_checkbox("termo_atendimento", 
                        ui.HTML("<span style='color: #78350f;'>Estou ciente de que o <strong>controle de atendimentos e financeiro</strong> são realizados através do app MedPIX</span>"),
                        value=False),
                    
                    ui.input_checkbox("termo_procedimentos", 
                        ui.HTML("<span style='color: #78350f;'>Estou ciente de que após o cadastro da clínica devo <strong>cadastrar os procedimentos</strong> oferecidos pela clínica</span>"),
                        value=False)
                ),

                ui.input_action_button("btn_cadastrar_clinica_auto", "✅ Cadastrar Clínica", 
                                      class_="btn-primary w-100 mt-3",
                                      style="padding: 1rem; font-size: 1.1rem; font-weight: 600;")
            )                          

    def render_content_by_type(tipo, user):
        """Renderiza conteúdo baseado no tipo de usuário"""
        if tipo == 'superusuario':
            return render_superuser_content()
        elif tipo == 'clinica':
            return render_clinica_content(user)
        return ui.div({"class": "card-custom"}, ui.h4("⚠️ Tipo de usuário inválido"))


    @output
    @render.ui
    def main_content():
        """Renderiza conteúdo principal com roteamento"""
        
        print("\n" + "="*60)
        print("🔍 RENDERIZANDO MAIN CONTENT")
        print("="*60)
        
        # --- 1. VERIFICA A URL PRIMEIRO (ANTES DE QUALQUER COISA) ---
        params = get_url_params()
        view = params.get("view")
        clinic_id_from_url = params.get("clinic_id")
        
        print(f"📋 Parâmetros da URL:")
        print(f"   view = {view}")
        print(f"   clinic_id = {clinic_id_from_url}")
        
        # --- 2. ROTA PÚBLICA: MOSTRA A VITRINE (SEM AUTENTICAÇÃO) ---
        if view == 'vitrine' and clinic_id_from_url:
            print(f"✅ ROTA PÚBLICA: Servindo Vitrine para Clínica ID: {clinic_id_from_url}")
            print("="*60 + "\n")
            return ui.output_ui("public_vitrine_page_ui")
        
        print("⚠️ Não é rota de vitrine pública, verificando autenticação...")
        
        # --- 3. ROTA PADRÃO: VERIFICA AUTENTICAÇÃO ---
        user = user_data()
        
        if not user:
            print("❌ Usuário não autenticado, mostrando tela de login")
            print("="*60 + "\n")
            return ui.div(
                {"style": "min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 2rem;"},
                ui.div(
                    {"style": "max-width: 450px; width: 100%;"},
                    ui.div(
                        {"class": "card-custom", "style": "box-shadow: 0 12px 48px rgba(0,0,0,0.12);"},
                        ui.output_ui("tela_login_cadastro")
                    )
                )
            )
        
        print(f"✅ Usuário autenticado: {user.get('nome')}")
        tipo = user.get('tipo_usuario', '')
        print(f"📌 Tipo de usuário: {tipo}")
        print("="*60 + "\n")

        if tipo == 'cliente':
            return render_cliente_content(user)

        # Busca nome adequado baseado no tipo
        if tipo == 'clinica':
            try:
                # DEBUG: Imprimir dados do usuário
                print(f"\n🔍 DEBUG HEADER CLÍNICA:")
                print(f"User ID: {user.get('id')}")
                print(f"User Nome: {user.get('nome')}")
                print(f"User CPF: {user.get('cpf')}")
                
                # Tenta buscar pela relação usuario_id
                usuario_id = user.get('id')
                clinica_result = supabase.table('clinicas').select('nome_fantasia, razao_social, cnpj').eq('usuario_id', usuario_id).execute()
                
                print(f"Resultado busca por usuario_id: {clinica_result.data}")
                
                # Se não encontrar, tenta pelo CPF/CNPJ
                if not clinica_result.data:
                    cpf_cnpj = user.get('cpf')
                    print(f"Tentando buscar por CNPJ: {cpf_cnpj}")
                    clinica_result = supabase.table('clinicas').select('nome_fantasia, razao_social, cnpj').eq('cnpj', cpf_cnpj).execute()
                    print(f"Resultado busca por CNPJ: {clinica_result.data}")
                
                if clinica_result.data:
                    clinica = clinica_result.data[0]
                    nome_fantasia = clinica.get('nome_fantasia', '').strip()
                    razao_social = clinica.get('razao_social', '').strip()
                    nome_exibicao = nome_fantasia or razao_social or user.get('nome', 'Clínica')
                    print(f"✅ Nome encontrado: {nome_exibicao}")
                else:
                    nome_exibicao = user.get('nome', 'Clínica')
                    print(f"⚠️ Clínica não encontrada, usando: {nome_exibicao}")
            except Exception as e:
                print(f"❌ Erro ao buscar clínica: {e}")
                nome_exibicao = user.get('nome', 'Clínica')
            
            tipo_icone = "🏥"
            tipo_label = "Clínica"
        elif tipo == 'superusuario':
            nome_exibicao = user.get('nome', 'Admin')
            tipo_icone = "👨‍💼"
            tipo_label = "Administrador"
        else:
            nome_exibicao = user.get('nome', 'Usuário')
            tipo_icone = "👤"
            tipo_label = tipo.title()

        return ui.div(
            ui.div(
                {"class": "app-header", "style": "padding: 1.5rem 2rem; background: #2D3748 !important; box-shadow: 0 4px 12px rgba(0,0,0,0.2);"},
                ui.row(
                    ui.column(2,
                        ui.img(src="https://github.com/AMalta/MedPIX/blob/0e7c9ede0d9f51ca7e552b59e999047894baae79/images/logoMP.jpeg", 
                               style="height: 80px; width: auto; object-fit: contain;")
                    ),
                    ui.column(7,
                        ui.div(
                            {"style": "display: flex; flex-direction: column; justify-content: center; height: 100%;"},
                            ui.h3(f"{tipo_icone} {nome_exibicao}", 
                                  style="margin: 0; color: #FFFFFF; font-weight: 700; font-size: 1.8rem; line-height: 1.2;"),
                            ui.p(tipo_label, 
                                 style="margin: 0.5rem 0 0 0; color: #1DD1A1; font-size: 1.1rem; font-weight: 600;")
                        )
                    ),
                    ui.column(3, 
                        ui.div(
                            {"style": "text-align: right; display: flex; align-items: center; justify-content: flex-end; height: 100%;"},
                            ui.input_action_button("btn_logout", "🚪 Sair", 
                                                  class_="btn btn-outline-light",
                                                  style="font-size: 1.1rem; padding: 0.7rem 1.8rem;")
                        )
                    )
                )
            ),
            render_content_by_type(tipo, user)
        )

    def render_superuser_content():
        """Renderiza dashboard do superusuário"""
        return ui.div(
            ui.h2("👨‍💼 Dashboard Administrativo"),
            
            # Cards de estatísticas
            ui.row(
                ui.column(3, ui.div({"class": "stat-card"},
                    ui.div(ui.output_text("stat_vendas"), {"class": "stat-value"}),
                    ui.div("💰 Vendas", {"class": "stat-label"})
                )),
                ui.column(3, ui.div({"class": "stat-card"},
                    ui.div(ui.output_text("stat_faturamento"), {"class": "stat-value"}),
                    ui.div("📊 Faturamento", {"class": "stat-label"})
                )),
                ui.column(3, ui.div({"class": "stat-card"},
                    ui.div(ui.output_text("stat_clientes"), {"class": "stat-value"}),
                    ui.div("📋 Clientes", {"class": "stat-label"})
                ))
            ),
            
            # Abas
            ui.div(
                {"class": "card-custom mt-4"},
                ui.navset_pill(
                    # Aba: Gráficos
                    ui.nav_panel("📊 Gráficos",
                        ui.row(
                            ui.column(6, ui.output_plot("grafico_vendas_periodo")),
                            ui.column(6, ui.output_plot("grafico_top_procedimentos"))
                        )
                    ),
                    # ========== NOVA ABA: CADASTRAR CLÍNICA ==========
                    ui.nav_panel("🏥 Cadastrar Clínica",
                        ui.div(
                            {"style": "max-width: 1400px; margin: 0 auto;"},
                            
                            # Header compacto
                            ui.div(
                                {"class": "card-custom", "style": "background: linear-gradient(135deg, #06b6d4, #0891b2); color: white; padding: 1rem; margin-bottom: 1rem;"},
                                ui.h5("🏥 Cadastro de Clínica", style="margin: 0;")
                            ),
                            
                            # Dados Básicos
                            ui.div(
                                {"class": "card-custom", "style": "padding: 1rem; margin-bottom: 1rem;"},
                                ui.h6("📋 Dados da Clínica", style="margin: 0 0 0.75rem 0; color: #0891b2; border-bottom: 2px solid #e0f2fe; padding-bottom: 0.5rem;"),
                                ui.row(
                                    ui.column(4, ui.input_text("cli_razao_super", "Razão Social*", placeholder="Nome oficial")),
                                    ui.column(4, ui.input_text("cli_fantasia_super", "Nome Fantasia", placeholder="Nome comercial")),
                                    ui.column(4, ui.input_text("cli_cnpj_super", "CNPJ*", placeholder="00.000.000/0000-00"))
                                ),
                                ui.row(
                                    ui.column(3, ui.input_text("cli_whatsapp_super", "WhatsApp*", placeholder="(00) 00000-0000")),
                                    ui.column(3, ui.input_text("cli_telefone_super", "Telefone", placeholder="(00) 0000-0000")),
                                    ui.column(3, ui.input_text("cli_email_super", "Email", placeholder="contato@clinica.com")),
                                    ui.column(3, ui.input_file("cli_logo_super", "Logo", accept=[".png", ".jpg", ".jpeg"], button_label="📷"))
                                )
                            ),
                            
                            # Localização
                            ui.div(
                                {"class": "card-custom", "style": "padding: 1rem; margin-bottom: 1rem;"},
                                ui.h6("📍 Localização", style="margin: 0 0 0.75rem 0; color: #0891b2; border-bottom: 2px solid #e0f2fe; padding-bottom: 0.5rem;"),
                                ui.row(
                                    ui.column(6, ui.input_text("cli_endereco_super", "Endereço Completo", placeholder="Rua, número, bairro")),
                                    ui.column(4, ui.input_text("cli_cidade_super", "Cidade*", placeholder="Nome da cidade")),
                                    ui.column(2, ui.input_select("cli_uf_super", "UF*", 
                                        choices={e: e if e else "Selecione" for e in ["", "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO"]}))
                                )
                            ),
                            
                            # Responsável
                            ui.div(
                                {"class": "card-custom", "style": "padding: 1rem; margin-bottom: 1rem;"},
                                ui.h6("👤 Responsável", style="margin: 0 0 0.75rem 0; color: #0891b2; border-bottom: 2px solid #e0f2fe; padding-bottom: 0.5rem;"),
                                ui.row(
                                    ui.column(6, ui.input_text("cli_responsavel_super", "Nome", placeholder="Nome do responsável")),
                                    ui.column(6, ui.input_text("cli_resp_contato_super", "Contato", placeholder="Telefone ou email"))
                                )
                            ),
                            
                            # Acesso e Financeiro lado a lado
                            ui.row(
                                # Acesso
                                ui.column(6,
                                    ui.div(
                                        {"class": "card-custom", "style": "padding: 1rem; margin-bottom: 1rem; height: 100%;"},
                                        ui.h6("🔑 Acesso ao Sistema", style="margin: 0 0 0.75rem 0; color: #0891b2; border-bottom: 2px solid #e0f2fe; padding-bottom: 0.5rem;"),
                                        ui.p("Login: CNPJ cadastrado", style="font-size: 0.85rem; color: #546E7A; margin: 0 0 0.5rem 0;"),
                                        ui.input_password("cli_senha_super", "Senha*", placeholder="Mínimo 6 caracteres")
                                    )
                                ),
                                # Comissão
                                ui.column(6,
                                    ui.div(
                                        {"class": "card-custom", "style": "padding: 1rem; margin-bottom: 1rem; height: 100%;"},
                                        ui.h6("💰 Comissão MedPIX", style="margin: 0 0 0.75rem 0; color: #0891b2; border-bottom: 2px solid #e0f2fe; padding-bottom: 0.5rem;"),
                                        ui.row(
                                            ui.column(4, ui.input_select("cli_tipo_comissao_super", "Tipo*", choices={"percentual": "%", "valor": "R$"})),
                                            ui.column(4, ui.input_numeric("cli_comissao_perc_super", "%", 12, min=0, max=100, step=0.5)),
                                            ui.column(4, ui.input_numeric("cli_comissao_valor_super", "R$", 0, min=0, step=10))
                                        )
                                    )
                                )
                            ),
                            
                            # Dados Bancários e PIX
                            ui.div(
                                {"class": "card-custom", "style": "padding: 1rem; margin-bottom: 1rem;"},
                                ui.h6("💳 Dados Financeiros", style="margin: 0 0 0.75rem 0; color: #0891b2; border-bottom: 2px solid #e0f2fe; padding-bottom: 0.5rem;"),
                                ui.row(
                                    ui.column(3, ui.input_text("cli_banco_super", "Banco", placeholder="Nome do banco")),
                                    ui.column(2, ui.input_text("cli_agencia_super", "Agência", placeholder="0000")),
                                    ui.column(3, ui.input_text("cli_conta_super", "Conta", placeholder="00000-0")),
                                    ui.column(4, ui.input_text("cli_titular_super", "Titular", placeholder="Nome do titular"))
                                ),
                                ui.row(
                                    ui.column(4, ui.input_text("cli_pix_super", "Chave PIX (Opcional)", placeholder="Chave adicional")),
                                    ui.column(4, ui.input_text("cli_pix_chave_super", "Chave PIX Pagamentos*", placeholder="Para receber pagamentos")),
                                    ui.column(2, ui.input_select("cli_pix_tipo_super", "Tipo*", choices={"cpf_cnpj": "CPF/CNPJ", "email": "Email", "telefone": "Tel", "aleatoria": "Aleatória"})),
                                    ui.column(2, ui.input_numeric("cli_cashback_perc_super", "Cashback %*", 4, min=0, max=50, step=0.5))
                                )
                            ),
                            
                            # Botões
                            ui.output_ui("btn_salvar_clinica_wrapper"),
                            ui.output_ui("btn_download_contrato_wrapper_super"),
                            
                            # Lista de Clínicas
                            ui.hr(style="margin: 2rem 0 1rem 0; border-color: #cbd5e1;"),
                            ui.h5("📋 Clínicas Cadastradas", style="margin: 0 0 1rem 0; color: #0f172a;"),
                            ui.output_ui("lista_clinicas_editar")
                        )
                    ),
                    # =================================================
                    
                    # Aba: Dados
                    ui.nav_panel("📋 Dados",
                        ui.div(
                            {"class": "card-custom", "style": "background: linear-gradient(135deg, #1DD1A1, #0D9488); color: white; padding: 1.5rem; margin-bottom: 1.5rem;"},
                            ui.h4("📊 Gestão Completa de Dados", style="margin: 0 0 0.5rem 0;"),
                            ui.p("Visualize, busque, edite e gerencie todos os registros do sistema", 
                                 style="margin: 0; opacity: 0.9;")
                        ),
                        
                        ui.navset_tab(
                            # ========== ABA USUÁRIOS ==========
                            ui.nav_panel("👥 Usuários",
                                ui.div(
                                    {"class": "card-custom"},
                                    ui.row(
                                        ui.column(6,
                                            ui.input_text("buscar_usuario_av", "🔍 Buscar", 
                                                         placeholder="Nome, email ou CPF...")
                                        ),
                                        ui.column(6,
                                            ui.input_select("filtro_tipo_usuario_av", "Filtrar por Tipo",
                                                choices={
                                                    "todos": "Todos",
                                                    "vendedor": "Vendedores",
                                                    "clinica": "Clínicas",
                                                    "superusuario": "Administradores"
                                                })
                                        )
                                    ),
                                    ui.hr(),
                                    ui.output_ui("tabela_usuarios_avancada")
                                )
                            ),
                            
                            # ========== ABA CLÍNICAS ==========
                            ui.nav_panel("🏥 Clínicas",
                                ui.div(
                                    {"class": "card-custom"},
                                    ui.row(
                                        ui.column(8,
                                            ui.input_text("buscar_clinica_av", "🔍 Buscar", 
                                                         placeholder="Nome, CNPJ ou cidade...")
                                        ),
                                        ui.column(4,
                                            ui.input_select("filtro_status_clinica_av", "Status",
                                                choices={
                                                    "todos": "Todos",
                                                    "ativo": "Ativas",
                                                    "inativo": "Inativas"
                                                })
                                        )
                                    ),
                                    ui.hr(),
                                    ui.output_ui("tabela_clinicas_avancada")
                                )
                            ),
                            
                            # ========== ABA CLIENTES ==========
                            ui.nav_panel("👤 Clientes",
                                ui.div(
                                    {"class": "card-custom"},
                                    ui.row(
                                        ui.column(8,
                                            ui.input_text("buscar_cliente_av", "🔍 Buscar", 
                                                         placeholder="Nome ou CPF...")
                                        ),
                                        ui.column(4,
                                            ui.input_select("filtro_status_cliente_av", "Status",
                                                choices={
                                                    "todos": "Todos",
                                                    "ativo": "Ativos",
                                                    "inativo": "Inativos"
                                                })
                                        )
                                    ),
                                    ui.hr(),
                                    ui.output_ui("tabela_clientes_avancada")
                                )
                            ),
                            
                            # ========== ABA VENDAS ==========
                            ui.nav_panel("💰 Vendas",
                                ui.div(
                                    {"class": "card-custom"},
                                    ui.row(
                                        ui.column(4,
                                            ui.input_text("buscar_venda_av", "🔍 Buscar", 
                                                         placeholder="Número da venda...")
                                        ),
                                        ui.column(4,
                                            ui.input_select("filtro_tipo_venda_av", "Tipo",
                                                choices={
                                                    "todos": "Todos",
                                                    "venda": "Vendas",
                                                    "orcamento": "Orçamentos"
                                                })
                                        ),
                                        ui.column(4,
                                            ui.input_select("filtro_status_venda_av", "Status",
                                                choices={
                                                    "todos": "Todos",
                                                    "concluido": "Concluídas",
                                                    "cancelado": "Canceladas"
                                                })
                                        )
                                    ),
                                    ui.hr(),
                                    ui.output_ui("tabela_vendas_avancada")
                                )
                            )
                        )
                    ),
                    # Aba: Confirmar Pagamentos
                    ui.nav_panel("💳 Confirmar Pagamentos",
                        ui.h4("Validar Pagamentos Informados"),
                        ui.p("Confirme os pagamentos informados pelos vendedores para liberar o atendimento nas clínicas.", 
                             style="color: #546E7A; margin-bottom: 1.5rem;"),
                        
                        # Estatísticas
                        ui.row(
                            ui.column(4, ui.div({"class": "stat-card", "style": "background: linear-gradient(135deg, #f59e0b, #d97706);"},
                                ui.div(ui.output_text("stat_aguardando_confirmacao"), {"class": "stat-value"}),
                                ui.div("⏳ Aguardando Confirmação", {"class": "stat-label"})
                            )),
                            ui.column(4, ui.div({"class": "stat-card", "style": "background: linear-gradient(135deg, #10b981, #059669);"},
                                ui.div(ui.output_text("stat_confirmados_hoje"), {"class": "stat-value"}),
                                ui.div("✅ Confirmados Hoje", {"class": "stat-label"})
                            )),
                            ui.column(4, ui.div({"class": "stat-card", "style": "background: linear-gradient(135deg, #6366f1, #4f46e5);"},
                                ui.div(ui.output_text("stat_total_confirmados"), {"class": "stat-value"}),
                                ui.div("📊 Total Confirmados", {"class": "stat-label"})
                            ))
                        ),
                        
                        ui.hr(),
                        
                        # Filtros
                        ui.row(
                            ui.column(6,
                                ui.input_select("filtro_confirmacao", "Filtrar",
                                    choices={
                                        "pendentes": "⏳ Aguardando Confirmação",
                                        "confirmados": "✅ Confirmados",
                                        "todos": "📋 Todos"
                                    })
                            ),
                            ui.column(6,
                                ui.input_text("buscar_confirmacao", "Buscar por Código ou Cliente",
                                             placeholder="Digite para buscar...")
                            )
                        ),
                        
                        ui.hr(),
                        
                        # Lista
                        ui.output_ui("lista_confirmacao_pagamentos")
                    ),
                    
                    # ========== NOVA ABA: PAGAR CLÍNICAS ==========
                    ui.nav_panel("🏥 Pagar Clínicas",
                        ui.h4("Efetuar Pagamento às Clínicas"),
                        ui.p("Registre os pagamentos realizados às clínicas pelos atendimentos concluídos", 
                             style="color: #546E7A; margin-bottom: 1.5rem;"),
                        
                        # Estatísticas
                        ui.row(
                            ui.column(4, ui.div({"class": "stat-card", "style": "background: linear-gradient(135deg, #f59e0b, #d97706);"},
                                ui.div(ui.output_text("stat_clinicas_pendentes"), {"class": "stat-value"}),
                                ui.div("⏳ Clínicas Pendentes", {"class": "stat-label"})
                            )),
                            ui.column(4, ui.div({"class": "stat-card", "style": "background: linear-gradient(135deg, #10b981, #059669);"},
                                ui.div(ui.output_text("stat_total_pagar_clinicas"), {"class": "stat-value"}),
                                ui.div("💰 Total a Pagar", {"class": "stat-label"})
                            )),
                            ui.column(4, ui.div({"class": "stat-card", "style": "background: linear-gradient(135deg, #6366f1, #4f46e5);"},
                                ui.div(ui.output_text("stat_clinicas_pagas_mes"), {"class": "stat-value"}),
                                ui.div("✅ Pagas este Mês", {"class": "stat-label"})
                            ))
                        ),
                        
                        ui.hr(),
                        
                        # Filtros
                        ui.row(
                            ui.column(6,
                                ui.input_select("filtro_pagamento_clinicas", "Filtrar",
                                    choices={
                                        "pendentes": "⏳ Aguardando Pagamento",
                                        "pagos": "✅ Pagos",
                                        "todos": "📋 Todos"
                                    })
                            ),
                            ui.column(6,
                                ui.input_text("buscar_pagamento_clinica", "Buscar Clínica",
                                             placeholder="Digite o nome...")
                            )
                        ),
                        
                        ui.hr(),
                        
                        # Lista
                        ui.output_ui("lista_pagamentos_clinicas")
                    ),                 
                    
                    # ========== NOVA ABA: CONTABILIDADE ==========
                    ui.nav_panel("📊 Contabilidade",
                        ui.h4("Controle Financeiro"),
                        ui.p("Visão geral da contabilidade do sistema", 
                             style="color: #546E7A; margin-bottom: 1.5rem;"),
                        
                        # Filtro de período
                        ui.row(
                            ui.column(4,
                                ui.input_select("periodo_contabil", "Período",
                                    choices={
                                        "mes_atual": "📅 Mês Atual",
                                        "mes_anterior": "📅 Mês Anterior",
                                        "trimestre": "📅 Últimos 3 Meses",
                                        "ano": "📅 Ano Atual",
                                        "tudo": "📅 Todo Período"
                                    })
                            ),
                            ui.column(4,
                                ui.input_date("data_inicio_contabil", "Data Início", 
                                             value=date.today().replace(day=1))
                            ),
                            ui.column(4,
                                ui.input_date("data_fim_contabil", "Data Fim", 
                                             value=date.today())
                            )
                        ),
                        
                        ui.hr(),
                        
                        # Cards de Resumo Financeiro
                        ui.h5("💰 Resumo Financeiro"),
                        ui.row(
                            ui.column(3, ui.div({"class": "stat-card", "style": "background: linear-gradient(135deg, #1DD1A1, #0D9488);"},
                                ui.div(ui.output_text("contab_faturamento_total"), {"class": "stat-value"}),
                                ui.div("📈 Faturamento Total", {"class": "stat-label"})
                            )),
                            ui.column(3, ui.div({"class": "stat-card", "style": "background: linear-gradient(135deg, #ef4444, #dc2626);"},
                                ui.div(ui.output_text("contab_pago_clinicas"), {"class": "stat-value"}),
                                ui.div("🏥 Pago às Clínicas", {"class": "stat-label"})
                            )),
                            ui.column(3, ui.div({"class": "stat-card", "style": "background: linear-gradient(135deg, #f59e0b, #d97706);"},
                                ui.div(ui.output_text("contab_cashback_pago"), {"class": "stat-value"}),
                                ui.div("💰 Cashback Pago", {"class": "stat-label"})
                            )),
                            ui.column(3, ui.div({"class": "stat-card", "style": "background: linear-gradient(135deg, #10b981, #059669);"},
                                ui.div(ui.output_text("contab_lucro_liquido"), {"class": "stat-value"}),
                                ui.div("💵 Lucro MedPIX", {"class": "stat-label"})
                            ))
                        ),
                        
                        ui.hr(),
                        
                        # Detalhamento
                        ui.h5("📋 Detalhamento"),
                        ui.navset_tab(
                            ui.nav_panel("📊 Resumo Geral",
                                ui.output_ui("contab_resumo_geral")
                            ),
                            ui.nav_panel("💳 Pagamentos Realizados",
                                ui.output_ui("contab_pagamentos_realizados")
                            ),
                            ui.nav_panel("⏳ Pagamentos Pendentes",
                                ui.output_ui("contab_pagamentos_pendentes")
                            ),
                            ui.nav_panel("📈 Gráficos",
                                ui.row(
                                    ui.column(6, ui.output_plot("contab_grafico_receitas")),
                                    ui.column(6, ui.output_plot("contab_grafico_comissoes"))
                                )
                           )
                        )
                    ),
                    # ========== NOVA ABA: PAGAR CASHBACK ==========
                    
                    ui.nav_panel("Pagar Cashback",
                        ui.h4("Efetuar Pagamento de Cashback aos Clientes"),
                        ui.p("Registre os pagamentos de cashback realizados aos clientes", 
                             style="color: #546E7A; margin-bottom: 1.5rem;"),
                        
                        # Estatasticas
                        ui.row(
                            ui.column(4, ui.div({"class": "stat-card", "style": "background: linear-gradient(135deg, #f59e0b, #d97706);"},
                                ui.div(ui.output_text("stat_clientes_cashback_pendente"), {"class": "stat-value"}),
                                ui.div("Clientes Pendentes", {"class": "stat-label"})
                            )),
                            ui.column(4, ui.div({"class": "stat-card", "style": "background: linear-gradient(135deg, #10b981, #059669);"},
                                ui.div(ui.output_text("stat_total_cashback_pagar"), {"class": "stat-value"}),
                                ui.div("Total a Pagar", {"class": "stat-label"})
                            )),
                            ui.column(4, ui.div({"class": "stat-card", "style": "background: linear-gradient(135deg, #6366f1, #4f46e5);"},
                                ui.div(ui.output_text("stat_cashback_pagos_mes"), {"class": "stat-value"}),
                                ui.div("Pagos este Mês", {"class": "stat-label"})
                            ))
                        ),
                        
                        ui.hr(),
                        
                        # Filtros
                        ui.row(
                            ui.column(6,
                                ui.input_select("filtro_cashback", "Filtrar",
                                    choices={
                                        "pendentes": "⏳ Aguardando Pagamento",
                                        "pagos": "✅ Pagos",
                                        "todos": "📋 Todos"
                                    })
                            ),
                            ui.column(6,
                                ui.input_text("buscar_cashback", "Buscar Cliente",
                                             placeholder="Digite o nome...")
                            )
                        ),
                        
                        ui.hr(),
                        
                        # Lista
                        ui.output_ui("lista_cashback_pagamentos")                    
                        
                    )
                )
            )    
        )    
        

    @reactive.Effect
    @reactive.event(input.btn_add_clinica_super)
    def add_clinica_super():
        try:
            if not supabase:
                ui.notification_show("❌ Supabase não configurado", type="error")
                return
            
            user = user_data()
            if not user:
                ui.notification_show("❌ Usuário não autenticado", type="error")
                return
            
            # Coleta dados
            razao = input.cli_razao_super()
            cnpj = input.cli_cnpj_super()
            whatsapp = input.cli_whatsapp_super()
            cidade = input.cli_cidade_super()
            uf = input.cli_uf_super()
            senha = input.cli_senha_super()
            
            print("\n" + "="*60)
            print("🏥 CADASTRO DE CLÍNICA (SUPERUSUÁRIO)")
            print("="*60)
            
            # Validações
            if not all([razao, cnpj, whatsapp, cidade, uf, senha]):
                ui.notification_show("⚠️ Preencha os campos obrigatórios!", type="warning")
                return
            
            if len(senha) < 6:
                ui.notification_show("⚠️ A senha deve ter no mínimo 6 caracteres!", type="warning")
                return
            
            # Limpa e valida CNPJ
            cnpj_limpo = limpar_documento(cnpj)
            
            if not validar_cnpj(cnpj_limpo):
                ui.notification_show("⚠️ CNPJ inválido!", type="warning")
                return
            
            # Verifica duplicidade
            check_user = supabase.table('usuarios').select('id').eq('cpf', cnpj_limpo).execute()
            if check_user.data:
                ui.notification_show("⚠️ Este CNPJ já está cadastrado!", type="warning")
                return
            
            # Processa logo
            logo_url = None
            file_info = input.cli_logo_super()
            if file_info:
                try:
                    file = file_info[0]
                    file_path = file['datapath']
                    with open(file_path, 'rb') as f:
                        logo_bytes = f.read()
                        logo_base64 = base64.b64encode(logo_bytes).decode()
                        logo_url = f"data:image/jpeg;base64,{logo_base64}"
                except Exception as e:
                    print(f"Erro ao processar logo: {e}")
            
            # Dados bancários e PIX
            dados_bancarios = {
                "banco": input.cli_banco_super(),
                "agencia": input.cli_agencia_super(),
                "conta": input.cli_conta_super(),
                "pix": input.cli_pix_super(),
                "titular": input.cli_titular_super()
            }
            
            dados_pix = {
                "chave": input.cli_pix_chave_super(),
                "tipo": input.cli_pix_tipo_super()
            }
            
            # Cria hash da senha
            senha_limpa = senha.strip()
            senha_hash = hash_senha(senha_limpa)
            
            print(f"Hash gerado: {senha_hash[:30]}...")
            
            # Cria usuário
            usuario_data_clinica = {
                "id": str(uuid.uuid4()),
                "nome": razao,
                "email": f"{cnpj_limpo}@medpix.local",
                "cpf": cnpj_limpo,
                "senha_hash": senha_hash,
                "tipo_usuario": "clinica",
                "ativo": True
            }
            
            usuario_result = supabase.table('usuarios').insert(usuario_data_clinica).execute()
            
            if not usuario_result.data:
                ui.notification_show("❌ Erro ao criar usuário!", type="error")
                return
            
            usuario_id = usuario_result.data[0]['id']
            
            # Cria clínica (SEM vendedor_id, pois é cadastro direto do super)
            clinica_data = {
                "usuario_id": usuario_id,
                "razao_social": razao,
                "nome_fantasia": input.cli_fantasia_super(),
                "cnpj": cnpj_limpo,
                "email": input.cli_email_super(),
                "telefone": input.cli_telefone_super(),
                "endereco_rua": input.cli_endereco_super(),
                "endereco_cidade": cidade,
                "endereco_estado": uf,
                "responsavel_nome": input.cli_responsavel_super(),
                "responsavel_contato": input.cli_resp_contato_super(),
                "logo_url": logo_url,
                "dados_bancarios": json.dumps(dados_bancarios),
                "dados_pix": json.dumps(dados_pix),
                "whatsapp": whatsapp,
                "ativo": True                
            }
            
            clinica_result = supabase.table('clinicas').insert(clinica_data).execute()
            
            if not clinica_result.data:
                ui.notification_show("❌ Erro ao cadastrar clínica!", type="error")
                return
            
            clinica_id = clinica_result.data[0]['id']
            
# ========== CRIAR COMISSÃO PADRÃO 12% ==========
            try:
                comissao_data = {
                    "clinica_id": clinica_id,
                    "tipo": "percentual",
                    "valor_percentual": 12  # PADRÃO 12% para MedPIX
                }
                
                print(f"\n{'='*60}")
                print(f"💼 CRIANDO COMISSÃO PARA CLÍNICA")
                print(f"{'='*60}")
                print(f"Clínica ID: {clinica_id}")
                print(f"Tipo: percentual")
                print(f"Percentual: 12%")
                
                comissao_result = supabase.table('comissoes_clinica').insert(comissao_data).execute()
                
                if comissao_result.data:
                    print(f"✅ Comissão criada com sucesso!")
                    print(f"Comissão ID: {comissao_result.data[0].get('id')}")
                else:
                    print(f"⚠️ Comissão não retornou dados, mas pode ter sido criada")
                
                print(f"{'='*60}\n")
                
            except Exception as e:
                print(f"\n{'='*60}")
                print(f"❌ ERRO AO CRIAR COMISSÃO!")
                print(f"{'='*60}")
                print(f"Erro: {e}")
                import traceback
                traceback.print_exc()
                print(f"{'='*60}\n")
                
                ui.notification_show(
                    f"⚠️ Clínica cadastrada, mas houve erro ao configurar comissão!\n"
                    f"Configure manualmente na área de edição.",
                    type="warning",
                    duration=10
                )

            
            # Prepara dados para contrato
            clinica_completa = {
                **clinica_result.data[0],
                'comissao_tipo': tipo_comissao,
                'comissao_perc': input.cli_comissao_perc_super() if tipo_comissao == 'percentual' else None,
                'comissao_valor': input.cli_comissao_valor_super() if tipo_comissao == 'valor' else None
            }
            
            # Gera contrato
            try:
                pdf_bytes = gerar_contrato_parceria(
                    clinica_completa,
                    formatar_cnpj(cnpj_limpo),
                    senha_limpa,
                    user.get('nome', 'Superusuário')
                )
                
                ultimo_contrato.set({
                    'pdf': pdf_bytes,
                    'filename': f"Contrato_{razao.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.pdf",
                    'clinica': razao,
                    'usuario': formatar_cnpj(cnpj_limpo),
                    'senha': senha_limpa
                })
                
                ui.notification_show(
                    f"✅ Clínica cadastrada com sucesso!\n🏥 CNPJ: {formatar_cnpj(cnpj_limpo)}\n🔑 Senha: {senha_limpa}\n📄 Contrato gerado!",
                    type="message",
                    duration=15
                )
                
                # Limpa formulário
                limpar_form_clinica_super()
                clinicas_trigger.set(clinicas_trigger() + 1)
                
            except Exception as e:
                print(f"Erro ao gerar contrato: {e}")
                ui.notification_show(
                    f"⚠️ Clínica cadastrada, mas erro ao gerar contrato: {str(e)}",
                    type="warning"
                )
        
        except Exception as e:
            print(f"Erro em add_clinica_super: {e}")
            import traceback
            traceback.print_exc()
            ui.notification_show(f"❌ Erro: {str(e)}", type="error")


    def limpar_form_clinica_super():
        """Limpa o formulário de cadastro de clínica do superusuário"""
        try:
            ui.update_text("cli_razao_super", value="")
            ui.update_text("cli_fantasia_super", value="")
            ui.update_text("cli_cnpj_super", value="")
            ui.update_text("cli_email_super", value="")
            ui.update_text("cli_telefone_super", value="")
            ui.update_text("cli_whatsapp_super", value="")
            ui.update_text("cli_cidade_super", value="")
            ui.update_select("cli_uf_super", selected="")
            ui.update_text("cli_endereco_super", value="")
            ui.update_text("cli_responsavel_super", value="")
            ui.update_text("cli_resp_contato_super", value="")
            ui.update_text("cli_senha_super", value="")
            ui.update_text("cli_banco_super", value="")
            ui.update_text("cli_agencia_super", value="")
            ui.update_text("cli_conta_super", value="")
            ui.update_text("cli_pix_super", value="")
            ui.update_text("cli_titular_super", value="")
            ui.update_text("cli_pix_chave_super", value="")
            ui.update_select("cli_pix_tipo_super", selected="cpf_cnpj")
            ui.update_select("cli_tipo_comissao_super", selected="percentual")
            ui.update_numeric("cli_comissao_perc_super", value=12)
            ui.update_numeric("cli_comissao_valor_super", value=0)
            ui.update_numeric("cli_cashback_perc_super", value=4)
        except:
            pass

    @output
    @render.ui
    def btn_salvar_clinica_wrapper():
        """Mostra botão de cadastrar ou atualizar baseado no modo"""
        clinica_id = clinica_editando_id()
        
        if clinica_id:
            # Modo edição
            return ui.div(
                ui.row(
                    ui.column(6,
                        ui.input_action_button("btn_update_clinica_super", "💾 Atualizar Clínica", 
                                              class_="btn-success mt-3 w-100")
                    ),
                    ui.column(6,
                        ui.input_action_button("btn_cancelar_edicao_clinica", "❌ Cancelar", 
                                              class_="btn-secondary mt-3 w-100")
                    )
                )
            )
        else:
            # Modo cadastro
            return ui.input_action_button("btn_add_clinica_super", "➕ Cadastrar Clínica e Gerar Contrato", 
                                          class_="btn-primary mt-3")
    
    @output
    @render.ui
    def lista_clinicas_editar():
        """Lista todas as clínicas com botão de editar"""
        try:
            # Trigger para atualizar
            _ = clinicas_trigger()
            
            if not supabase:
                return ui.div()
            
            # Busca todas as clínicas
            result = supabase.table('clinicas').select(
                '*, comissoes_clinica(*), usuarios!clinicas_usuario_id_fkey(ativo)'
            ).order('id', desc=True).execute()
            
            if not result.data:
                return ui.div(
                    {"style": "text-align: center; padding: 2rem; color: #546E7A;"},
                    ui.p("Nenhuma clínica cadastrada ainda.", style="font-size: 1.1rem;")
                )
            
            cards = []
            for clinica in result.data:
                clinica_id = clinica['id']
                razao = clinica.get('razao_social', 'N/A')
                fantasia = clinica.get('nome_fantasia', '')
                cnpj = formatar_cnpj(clinica.get('cnpj', ''))
                cidade = clinica.get('endereco_cidade', '')
                uf = clinica.get('endereco_estado', '')
                whatsapp = formatar_whatsapp(clinica.get('whatsapp', ''))
                ativo = clinica.get('usuarios', {}).get('ativo', True)
                
                # Comissão
                comissao_info = clinica.get('comissoes_clinica', [])
                if comissao_info and len(comissao_info) > 0:
                    comissao = comissao_info[0]
                    if comissao.get('tipo') == 'percentual':
                        comissao_texto = f"{comissao.get('valor_percentual', 0)}%"
                    else:
                        comissao_texto = formatar_moeda(comissao.get('valor_fixo', 0))
                else:
                    comissao_texto = "Não definida"
                
                # Status
                status_badge = "🟢 Ativa" if ativo else "🔴 Inativa"
                status_color = "#16a34a" if ativo else "#dc2626"
                
                card = ui.div(
                    {"class": "card-custom", "style": f"margin-bottom: 1rem; border-left: 4px solid {status_color};"},
                    ui.row(
                        ui.column(9,
                            ui.h6(f"🏥 {razao}", style="margin: 0 0 0.5rem 0; font-weight: bold;"),
                            ui.div(
                                ui.p(f"📌 {fantasia}" if fantasia else "", 
                                     style="margin: 0; font-size: 0.9rem; color: #546E7A;"),
                                ui.p(f"📄 CNPJ: {cnpj}", style="margin: 0.25rem 0; font-size: 0.9rem;"),
                                ui.p(f"📍 {cidade}/{uf}" if cidade else "", style="margin: 0.25rem 0; font-size: 0.9rem;"),
                                ui.p(f"📱 {whatsapp}", style="margin: 0.25rem 0; font-size: 0.9rem;"),
                                ui.p(f"💳 Comissão: {comissao_texto}", style="margin: 0.25rem 0; font-size: 0.9rem; font-weight: 600;"),
                                ui.tags.span(status_badge, style=f"color: {status_color}; font-weight: 600; font-size: 0.85rem;")
                            )
                        ),
                        ui.column(3,
                            ui.div(
                                {"style": "display: flex; flex-direction: column; gap: 0.5rem; align-items: stretch;"},
                                ui.input_action_button(
                                    f"btn_editar_clinica_{clinica_id.replace('-', '_')}",
                                    "✏️ Editar",
                                    class_="btn-sm btn-outline-primary w-100"
                                )
                            )
                        )
                    )
                )
                cards.append(card)
            
            return ui.div(*cards)
            
        except Exception as e:
            print(f"Erro em lista_clinicas_editar: {e}")
            import traceback
            traceback.print_exc()
            return ui.div(ui.p(f"Erro: {str(e)}", style="color: red;"))
    
    def preencher_form_clinica(clinica_id):
        """Preenche o formulário com os dados da clínica para edição"""
        try:
            if not supabase:
                return
            
            # Busca dados da clínica
            result = supabase.table('clinicas').select(
                '*, comissoes_clinica(*), cashback_clinica(*), usuarios!clinicas_usuario_id_fkey(*)'
            ).eq('id', clinica_id).execute()
            
            if not result.data:
                ui.notification_show("❌ Clínica não encontrada!", type="error")
                return
            
            clinica = result.data[0]
            
            # Preenche campos básicos
            ui.update_text("cli_razao_super", value=clinica.get('razao_social', ''))
            ui.update_text("cli_fantasia_super", value=clinica.get('nome_fantasia', ''))
            ui.update_text("cli_cnpj_super", value=formatar_cnpj(clinica.get('cnpj', '')))
            ui.update_text("cli_email_super", value=clinica.get('email', ''))
            ui.update_text("cli_telefone_super", value=clinica.get('telefone', ''))
            ui.update_text("cli_whatsapp_super", value=clinica.get('whatsapp', ''))
            ui.update_text("cli_cidade_super", value=clinica.get('endereco_cidade', ''))
            ui.update_select("cli_uf_super", selected=clinica.get('endereco_estado', ''))
            ui.update_text("cli_endereco_super", value=clinica.get('endereco_rua', ''))
            ui.update_text("cli_responsavel_super", value=clinica.get('responsavel_nome', ''))
            ui.update_text("cli_resp_contato_super", value=clinica.get('responsavel_contato', ''))
            
            # Dados bancários
            try:
                dados_bancarios = json.loads(clinica.get('dados_bancarios', '{}')) if clinica.get('dados_bancarios') else {}
                ui.update_text("cli_banco_super", value=dados_bancarios.get('banco', ''))
                ui.update_text("cli_agencia_super", value=dados_bancarios.get('agencia', ''))
                ui.update_text("cli_conta_super", value=dados_bancarios.get('conta', ''))
                ui.update_text("cli_pix_super", value=dados_bancarios.get('pix', ''))
                ui.update_text("cli_titular_super", value=dados_bancarios.get('titular', ''))
            except:
                pass
            
            # Dados PIX
            try:
                dados_pix = json.loads(clinica.get('dados_pix', '{}')) if clinica.get('dados_pix') else {}
                ui.update_text("cli_pix_chave_super", value=dados_pix.get('chave', ''))
                ui.update_select("cli_pix_tipo_super", selected=dados_pix.get('tipo', 'cpf_cnpj'))
            except:
                pass
            
            # Comissão
            comissoes = clinica.get('comissoes_clinica', [])
            if comissoes and len(comissoes) > 0:
                comissao = comissoes[0]
                tipo_com = comissao.get('tipo', 'percentual')
                ui.update_select("cli_tipo_comissao_super", selected=tipo_com)
                
                if tipo_com == 'percentual':
                    ui.update_numeric("cli_comissao_perc_super", value=float(comissao.get('valor_percentual', 0)))
                    ui.update_numeric("cli_comissao_valor_super", value=0)
                else:
                    ui.update_numeric("cli_comissao_valor_super", value=float(comissao.get('valor_fixo', 0)))
                    ui.update_numeric("cli_comissao_perc_super", value=0)
            
            # Cashback
            cashback = clinica.get('cashback_clinica', [])
            if cashback:
                if isinstance(cashback, list) and len(cashback) > 0:
                    ui.update_numeric("cli_cashback_perc_super", value=float(cashback[0].get('percentual', 5)))
                elif isinstance(cashback, dict):
                    ui.update_numeric("cli_cashback_perc_super", value=float(cashback.get('percentual', 5)))
            
            # Define modo edição
            clinica_editando_id.set(clinica_id)
            
            ui.notification_show(
                f"✏️ Editando clínica: {clinica.get('razao_social', '')}\n"
                "Modifique os campos e clique em 'Atualizar Clínica'",
                type="message",
                duration=8
            )
            
        except Exception as e:
            print(f"Erro em preencher_form_clinica: {e}")
            import traceback
            traceback.print_exc()
            ui.notification_show(f"❌ Erro ao carregar dados: {str(e)}", type="error")
    
    @reactive.Effect
    def _monitor_botoes_editar():
        """Monitora cliques nos botões de editar clínicas"""
        try:
            _ = clinicas_trigger()
            
            if not supabase:
                return
            
            result = supabase.table('clinicas').select('id').execute()
            
            if not result.data:
                return
            
            for clinica in result.data:
                clinica_id = clinica['id']
                btn_id = f"btn_editar_clinica_{clinica_id.replace('-', '_')}"
                
                @reactive.Effect
                @reactive.event(input[btn_id], ignore_none=True)
                def _editar_esta_clinica(cid=clinica_id):
                    preencher_form_clinica(cid)
        except:
            pass
    
    @reactive.Effect
    @reactive.event(input.btn_cancelar_edicao_clinica, ignore_none=True)
    def _cancelar_edicao_clinica():
        """Cancela a edição e limpa o formulário"""
        try:
            clinica_editando_id.set(None)
            limpar_form_clinica_super()
            ui.notification_show("❌ Edição cancelada!", type="warning", duration=3)
        except:
            pass
    
    @reactive.Effect
    @reactive.event(input.btn_update_clinica_super, ignore_none=True)
    def _update_clinica_super():
        """Atualiza dados da clínica"""
        try:
            clinica_id = clinica_editando_id()
            
            if not clinica_id or not supabase:
                ui.notification_show("❌ Erro: clínica não identificada!", type="error")
                return
            
            user = user_data()
            if not user:
                ui.notification_show("❌ Usuário não autenticado", type="error")
                return
            
            print(f"\n{'='*60}")
            print(f"💾 ATUALIZANDO CLÍNICA: {clinica_id}")
            print(f"{'='*60}")
            
            razao = input.cli_razao_super()
            cnpj = input.cli_cnpj_super()
            whatsapp = input.cli_whatsapp_super()
            cidade = input.cli_cidade_super()
            uf = input.cli_uf_super()
            senha = input.cli_senha_super()
            
            if not all([razao, cnpj, whatsapp, cidade, uf]):
                ui.notification_show("⚠️ Preencha os campos obrigatórios!", type="warning")
                return
            
            cnpj_limpo = limpar_documento(cnpj)
            
            if not validar_cnpj(cnpj_limpo):
                ui.notification_show("⚠️ CNPJ inválido!", type="warning")
                return
            
            logo_url = None
            file_info = input.cli_logo_super()
            if file_info:
                try:
                    file = file_info[0]
                    file_path = file['datapath']
                    with open(file_path, 'rb') as f:
                        logo_bytes = f.read()
                        logo_base64 = base64.b64encode(logo_bytes).decode()
                        logo_url = f"data:image/jpeg;base64,{logo_base64}"
                except Exception as e:
                    print(f"Erro ao processar logo: {e}")
            
            dados_bancarios = {
                "banco": input.cli_banco_super(),
                "agencia": input.cli_agencia_super(),
                "conta": input.cli_conta_super(),
                "pix": input.cli_pix_super(),
                "titular": input.cli_titular_super()
            }
            
            dados_pix = {
                "chave": input.cli_pix_chave_super(),
                "tipo": input.cli_pix_tipo_super()
            }
            
            clinica_update = {
                "razao_social": razao,
                "nome_fantasia": input.cli_fantasia_super(),
                "cnpj": cnpj_limpo,
                "email": input.cli_email_super(),
                "telefone": input.cli_telefone_super(),
                "endereco_rua": input.cli_endereco_super(),
                "endereco_cidade": cidade,
                "endereco_estado": uf,
                "responsavel_nome": input.cli_responsavel_super(),
                "responsavel_contato": input.cli_resp_contato_super(),
                "dados_bancarios": json.dumps(dados_bancarios),
                "dados_pix": json.dumps(dados_pix),
                "whatsapp": whatsapp
            }
            
            if logo_url:
                clinica_update["logo_url"] = logo_url
            
            supabase.table('clinicas').update(clinica_update).eq('id', clinica_id).execute()
            
            tipo_comissao = input.cli_tipo_comissao_super()
            comissao_data = {"tipo": tipo_comissao}
            
            if tipo_comissao == "percentual":
                comissao_data["valor_percentual"] = input.cli_comissao_perc_super()
                comissao_data["valor_fixo"] = 0
            else:
                comissao_data["valor_fixo"] = input.cli_comissao_valor_super()
                comissao_data["valor_percentual"] = 0
            
            comissao_result = supabase.table('comissoes_clinica').select('id').eq('clinica_id', clinica_id).execute()
            
            if comissao_result.data:
                supabase.table('comissoes_clinica').update(comissao_data).eq('clinica_id', clinica_id).execute()
            else:
                comissao_data['clinica_id'] = clinica_id
                supabase.table('comissoes_clinica').insert(comissao_data).execute()
            
            cashback_perc = input.cli_cashback_perc_super()
            if cashback_perc and cashback_perc > 0:
                cashback_result = supabase.table('cashback_clinica').select('id').eq('clinica_id', clinica_id).execute()
                
                if cashback_result.data:
                    supabase.table('cashback_clinica').update({'percentual': cashback_perc}).eq('clinica_id', clinica_id).execute()
                else:
                    supabase.table('cashback_clinica').insert({'clinica_id': clinica_id, 'percentual': cashback_perc}).execute()
            
            if senha and len(senha) >= 6:
                clinica_data = supabase.table('clinicas').select('usuario_id').eq('id', clinica_id).execute()
                if clinica_data.data:
                    usuario_id = clinica_data.data[0]['usuario_id']
                    senha_hash = hash_senha(senha.strip())
                    supabase.table('usuarios').update({'senha_hash': senha_hash}).eq('id', usuario_id).execute()
                    print(f"✅ Senha atualizada para usuário {usuario_id}")
            
            print(f"✅ Clínica atualizada com sucesso!")
            
            ui.notification_show(f"✅ Clínica atualizada!\n🏥 {razao}", type="message", duration=8)
            
            clinica_editando_id.set(None)
            limpar_form_clinica_super()
            clinicas_trigger.set(clinicas_trigger() + 1)
            
        except Exception as e:
            print(f"❌ Erro em _update_clinica_super: {e}")
            import traceback
            traceback.print_exc()
            ui.notification_show(f"❌ Erro ao atualizar: {str(e)}", type="error")

    @output
    @render.ui
    def btn_download_contrato_wrapper_super():
        """Mostra botão de download do contrato no ambiente super"""
        contrato = ultimo_contrato()
        if not contrato:
            return ui.div()
        
        return ui.div(
            {"class": "mt-3 p-3", "style": "background: #dcfce7; border-radius: 0.5rem; border: 2px solid #16a34a;"},
            ui.row(
                ui.column(8,
                    ui.h5("✅ Contrato Pronto!", style="color: #16a34a; margin: 0;"),
                    ui.p(f"Clínica: {contrato['clinica']}", style="margin: 0.5rem 0 0 0; font-size: 0.9rem;"),
                    ui.p(f"Login: {contrato['usuario']} | Senha: {contrato['senha']}", 
                         style="margin: 0.25rem 0 0 0; font-size: 0.85rem; font-family: monospace; color: #15803d;")
                ),
                ui.column(4,
                    ui.download_button("btn_download_contrato", "📥 Baixar Contrato PDF",
                                      class_="btn btn-success w-100 mt-2")
                )
            )
        )


    
    # ========== 9. ESTATASTICAS DE CASHBACK (SUPERUSUARIO) ==========
    @output
    @render.text
    def stat_clientes_cashback_pendente():
        try:
            if not supabase:
                return "0"
            
            result = supabase.table('cashback_pagamentos').select(
                'cliente_id'
            ).eq('pago', False).execute()
            
            if not result.data:
                return "0"
            
            clientes = set([c['cliente_id'] for c in result.data])
            return str(len(clientes))
        except:
            return "0"


    @output
    @render.text
    def stat_total_cashback_pagar():
        try:
            if not supabase:
                return "R$ 0,00"
            
            result = supabase.table('cashback_pagamentos').select('valor').eq('pago', False).execute()
            
            if not result.data:
                return "R$ 0,00"
            
            total = sum([float(c.get('valor', 0) or 0) for c in result.data])
            return formatar_moeda(total)
        except:
            return "R$ 0,00"


    @output
    @render.text
    def stat_cashback_pagos_mes():
        try:
            if not supabase:
                return "0"
            
            primeiro_dia = date.today().replace(day=1)
            
            result = supabase.table('cashback_pagamentos').select(
                'id', count='exact'
            ).eq('pago', True).gte('data_pagamento', f'{primeiro_dia}T00:00:00').execute()
            
            return str(result.count or 0)
        except:
            return "0"

# ========== 10. MODAL PARA UPLOAD DE COMPROVANTE ==========
    @output
    @render.ui
    def comprovante_upload_modal_ui():
        venda_id = venda_id_para_comprovante()
        if not venda_id:
            return ui.div() # Retorna vazio se não houver venda selecionada

        # Busca dados da venda para exibir no modal
        venda_info = None
        try:
            if supabase:
                venda_res = supabase.table('vendas').select('numero_venda, valor_total').eq('id', venda_id).single().execute()
                if venda_res.data:
                    venda_info = venda_res.data
        except Exception as e:
            print(f"Aviso: Erro ao buscar dados da venda para modal comprovante: {e}")

        numero_venda = venda_info.get('numero_venda', 'N/A') if venda_info else 'N/A'
        valor_venda = formatar_moeda(venda_info.get('valor_total', 0)) if venda_info else 'N/A'

        # Cria o HTML do modal
        modal_id = f"upload_modal_{venda_id}"
        return ui.div(
            {"id": modal_id, "style": """
                position: fixed; top: 0; left: 0; width: 100%; height: 100%;
                background: rgba(0,0,0,0.8); z-index: 10001; /* Z-index alto */
                display: flex; align-items: center; justify-content: center;
                padding: 1rem;
            """},
            ui.div(
                {"style": """
                    background: white; border-radius: 1rem; padding: 2rem;
                    max-width: 95%; width: 500px;
                    box-shadow: 0 5px 15px rgba(0,0,0,0.3);
                """},
                ui.h3("✉️ Enviar Comprovante", style="color: #f59e0b; margin-bottom: 1rem; text-align: center;"),
                ui.p(f"Compra: {numero_venda} ({valor_venda})", style="text-align: center; color: #546E7A; margin-bottom: 1.5rem;"),
                ui.p("Selecione a imagem ou PDF do seu comprovante de pagamento PIX.", style="font-size: 0.9rem; margin-bottom: 1rem;"),
                ui.input_file(
                    "upload_comprovante_input", # ID fixo para o input
                    label="", # Sem label visível aqui
                    accept=[".png", ".jpg", ".jpeg", ".pdf"], # Aceita imagens e PDF
                    multiple=False,
                    button_label="Selecionar Arquivo..."
                ),
                # Placeholder para mostrar nome do arquivo selecionado
                ui.output_ui("nome_arquivo_comprovante"),
                ui.hr(style="margin: 1.5rem 0;"),
                ui.div(
                    {"style": "display: flex; gap: 1rem;"},
                    ui.input_action_button(
                        "btn_confirmar_envio_comprovante",
                        "✅ Enviar Comprovante",
                        class_="btn-success", # Botão verde
                        style="flex: 1; font-weight: 600;"
                    ),
                    ui.tags.button(
                        "Cancelar",
                        class_="btn btn-secondary", # Botão cinza
                        onclick=f"Shiny.setInputValue('cancelar_envio_comprovante', Math.random(), {{priority: 'event'}})", # Trigger para fechar
                        style="flex: 1;"
                    )
                )
            )
        )

    # Helper para mostrar nome do arquivo selecionado
    @output
    @render.ui
    def nome_arquivo_comprovante():
        file_info = input.upload_comprovante_input()
        if file_info:
            return ui.p(f"Arquivo selecionado: {file_info[0]['name']}", style="font-size: 0.85rem; color: #10b981; margin-top: 0.5rem; text-align: center;")
        return ui.div()        

    @output
    @render.ui
    def lista_cashback_pagamentos():
        """Lista completa de cashback para o superusuário gerenciar"""
        try:
            if not supabase:
                return ui.div()

            # Busca todos os registros de cashback
            query = supabase.table('cashback_pagamentos').select(
                '*, clientes(nome_completo, cpf, usuario_id), vendas(numero_venda, criado_em, comprovante_url)'  # ← ADICIONADO comprovante_url
            )

            # Aplica filtros
            filtro = input.filtro_cashback()
            if filtro == "pendentes":
                query = query.eq('pago', False)
            elif filtro == "pagos":
                query = query.eq('pago', True)

            # Busca por nome
            busca = input.buscar_cashback()
            if busca:
                clientes_result = supabase.table('clientes').select('id').ilike(
                    'nome_completo', f'%{busca}%'
                ).execute()

                if clientes_result.data:
                    cliente_ids = [c['id'] for c in clientes_result.data]
                    query = query.in_('cliente_id', cliente_ids)

            result = query.order('criado_em', desc=True).execute()

            if not result.data:
                return ui.div(
                    {"style": "text-align: center; padding: 3rem; color: #94a3b8;"},
                    ui.h5("🔭 Nenhum cashback encontrado"),
                    ui.p("Os cashbacks aparecerão aqui após as compras dos clientes")
                )

            # Agrupa por cliente
            cashback_por_cliente = {}

            for cash in result.data:
                cliente_id = cash.get('cliente_id')
                cliente = cash.get('clientes', {})
                cliente_nome = cliente.get('nome_completo', 'N/A')

                if cliente_id not in cashback_por_cliente:
                    usuario_id = cliente.get('usuario_id')
                    pix_chave = None
                    if usuario_id:
                        try:
                            usuario_result = supabase.table('usuarios').select('pix_chave').eq('id', usuario_id).execute()
                            if usuario_result.data:
                                pix_chave = usuario_result.data[0].get('pix_chave')
                        except Exception as pix_err:
                            print(f"Erro ao buscar PIX para usuario {usuario_id}: {pix_err}")
                            pass

                    cashback_por_cliente[cliente_id] = {
                        'nome': cliente_nome,
                        'cpf': cliente.get('cpf', ''),
                        'pix_chave': pix_chave,
                        'cashbacks': [],
                        'total_pendente': 0,
                        'total_pago': 0
                    }

                cashback_por_cliente[cliente_id]['cashbacks'].append(cash)

                if cash.get('pago'):
                    cashback_por_cliente[cliente_id]['total_pago'] += float(cash.get('valor', 0) or 0)
                else:
                    cashback_por_cliente[cliente_id]['total_pendente'] += float(cash.get('valor', 0) or 0)

            # Cria cards
            cards = []
            for cliente_id, dados in cashback_por_cliente.items():
                if filtro == "pendentes" and dados['total_pendente'] == 0:
                    continue
                elif filtro == "pagos" and dados['total_pago'] == 0 and dados['total_pendente'] > 0:
                    continue

                cor_border = "#10b981" if dados['total_pendente'] == 0 else "#f59e0b"

                # ========== MONTA LISTA DE COMPROVANTES ==========
                comprovantes_html = []
                for idx, cash in enumerate(dados['cashbacks']):
                    venda = cash.get('vendas', {})
                    numero_venda = venda.get('numero_venda', 'N/A')
                    comprovante_url = venda.get('comprovante_url')
                    
                    if comprovante_url:
                        comprovantes_html.append(
                            ui.div(
                                {"style": "margin-bottom: 0.5rem;"},
                                ui.p(f"📄 {numero_venda}:", style="margin: 0; font-size: 0.85rem; font-weight: 600; color: #2D3748;"),
                                ui.tags.a(
                                    "👁️ Ver Comprovante",
                                    href=comprovante_url,
                                    target="_blank",
                                    class_="btn btn-sm btn-info",
                                    style="margin-top: 0.25rem; padding: 0.25rem 0.75rem; font-size: 0.75rem;"
                                )
                            )
                        )
                # =================================================

                card = ui.div(
                    {"class": "card-custom", "style": f"margin-bottom: 1rem; border-left: 4px solid {cor_border};"},
                    ui.row(
                        ui.column(7,  # ← REDUZIDO de 8 para 7
                            ui.h5(dados['nome'], style="margin: 0 0 0.5rem 0;"),
                            ui.p(f"📄 CPF: {formatar_cpf(dados['cpf'])}", 
                                  style="margin: 0.25rem 0; font-size: 0.9rem;"),
                            ui.p(f"💳 PIX: {dados['pix_chave'] or '❌ Não cadastrado'}",
                                  style="margin: 0.25rem 0; font-size: 0.9rem; color: #10b981; font-weight: 600;"),
                            ui.p(f"🛒 Compras: {len(dados['cashbacks'])}",
                                  style="margin: 0.25rem 0; font-size: 0.9rem;"),
                            ui.p(f"⏳ Pendente: {formatar_moeda(dados['total_pendente'])}", 
                                  style="margin: 0.25rem 0; font-size: 0.9rem; color: #f59e0b; font-weight: 600;"),
                            ui.p(f"✅ Pago: {formatar_moeda(dados['total_pago'])}", 
                                  style="margin: 0.25rem 0; font-size: 0.9rem; color: #10b981;")
                        ),
                        # ========== NOVA COLUNA: COMPROVANTES ==========
                        ui.column(2,
                            ui.div(
                                {"style": "background: #f8fafc; padding: 0.75rem; border-radius: 0.5rem; border: 1px solid #e2e8f0;"},
                                ui.h6("📎 Comprovantes", style="margin: 0 0 0.75rem 0; font-size: 0.85rem; color: #546E7A;"),
                                *comprovantes_html if comprovantes_html else [
                                    ui.p("Nenhum comprovante", style="margin: 0; font-size: 0.75rem; color: #94a3b8; text-align: center;")
                                ]
                            )
                        ),
                        # ===============================================
                        ui.column(3,  # ← REDUZIDO de 4 para 3
                            ui.div(
                                {"style": "text-align: right;"},
                                ui.tags.button(
                                    "📲 Gerar QR Code PIX",
                                    class_="btn btn-info w-100 mb-2",
                                    onclick=f"Shiny.setInputValue('{session.ns('gerar_pix_cashback_id')}', '{cliente_id}', {{priority: 'event'}})",
                                    style="font-weight: 600; padding: 0.75rem; font-size: 0.85rem;"
                                ) if dados['total_pendente'] > 0 and dados['pix_chave'] else None,
                                ui.tags.button(
                                    "💸 Efetuar Pagamento",
                                    class_="btn btn-success w-100",
                                    onclick=f"Shiny.setInputValue('{session.ns('pagar_cashback_id')}', '{cliente_id}', {{priority: 'event'}})",
                                    style="font-weight: 600; padding: 0.75rem; font-size: 0.85rem;"
                                ) if dados['total_pendente'] > 0 else ui.div(
                                    {"class": "btn btn-secondary w-100 disabled", "style": "font-weight: 600; padding: 0.75rem; font-size: 0.85rem;"},
                                    "✅ Tudo Pago"
                                )
                            )
                        )
                    )
                )
                cards.append(card)

            if not cards:
                return ui.div(
                    {"style": "text-align: center; padding: 3rem; color: #94a3b8;"},
                    ui.h5("🔭 Nenhum cashback com os filtros aplicados")
                )

            return ui.div(*cards)

        except Exception as e:
            print(f"❌ Erro lista_cashback_pagamentos: {e}")
            import traceback
            traceback.print_exc()
            return ui.div(ui.p(f"Erro ao listar cashbacks: {str(e)}", style="color: red; padding: 1rem;"))

    @reactive.Effect
    def _monitor_pagamento_cashback_click():
        """Registra pagamento de cashback ao cliente"""
        try:
            cliente_id = None
            try:
                cliente_id = input.pagar_cashback_id()
            except Exception:
                return
            
            if not cliente_id:
                return
            
            print(f"\n💸 PAGAR CASHBACK - DEBUG")
            print(f"{'='*60}")
            print(f"Cliente ID: {cliente_id}")
            
            user = user_data()
            if not user or not supabase:
                return
            
            # Busca cashbacks pendentes para o cliente
            cashback_result = supabase.table('cashback_pagamentos').select('*').eq(
                'cliente_id', cliente_id
            ).eq('pago', False).execute()
            
            if not cashback_result.data:
                ui.notification_show("⚠️ Nenhum cashback pendente!", type="warning")
                return
            
            # Busca o nome do cliente
            cliente_result = supabase.table('clientes').select(
                'nome_completo, usuarios!clientes_usuario_id_fkey(telefone)'
            ).eq('id', cliente_id).execute()
            
            cliente_nome = cliente_result.data[0].get('nome_completo', 'N/A') if cliente_result.data else 'N/A'
            cliente_telefone = None
            if cliente_result.data and cliente_result.data[0].get('usuarios'):
                cliente_telefone = cliente_result.data[0]['usuarios'].get('telefone')
            
            total_pago = 0
            
            # Itera sobre os cashbacks pendentes e atualiza cada um
            for cashback in cashback_result.data:
                valor_cashback = float(cashback.get('valor', 0) or 0)
                
                supabase.table('cashback_pagamentos').update({
                    'pago': True,
                    'data_pagamento': datetime.now().isoformat(),
                }).eq('id', cashback['id']).execute()
                
                # Notifica cliente
                if cliente_telefone:
                    try:
                        nome_primeiro = cliente_nome.split()[0] if cliente_nome else 'Cliente'
                        
                        mensagem = f"""
    💰 *CASHBACK RECEBIDO!*

    Olá, *{nome_primeiro}*!

    Você acaba de receber {formatar_moeda(valor_cashback)} de cashback na sua conta PIX!

    Continue comprando para aumentar seu cashback nas próximas compras!

    _Mensagem enviada via MedPIX_
                        """
                        
                        enviar_whatsapp(cliente_telefone, mensagem)
                        print(f"✅ Cliente notificado sobre cashback de {formatar_moeda(valor_cashback)}")
                    except Exception as e:
                        print(f"⚠️ Erro ao notificar: {e}")
                
                total_pago += valor_cashback
            
            print(f"✅ {len(cashback_result.data)} cashback(s) pagos!")
            print(f"💰 Total: {formatar_moeda(total_pago)}")
            print(f"{'='*60}\n")
            
            # ⭐ CRÍTICO: ATUALIZA O TRIGGER PARA FORÇAR REFRESH DOS CARDS
            cashback_trigger.set(cashback_trigger() + 1)
            
            ui.notification_show(
                f"✅ Cashback pago com sucesso!\n"
                f"👤 Cliente: {cliente_nome}\n"
                f"💰 Total: {formatar_moeda(total_pago)}",
                type="message",
                duration=8
            )
            
        except Exception as e:
            print(f"❌ Erro em _monitor_pagamento_cashback_click: {e}")
            import traceback
            traceback.print_exc()
            ui.notification_show(f"❌ Erro ao pagar cashback: {str(e)}", type="error")
 
    @reactive.Effect
    @reactive.event(input.btn_limpar_carrinho_cliente)
    def limpar_carrinho_cliente():
        """Limpa todo o carrinho do cliente"""
        try:
            print(f"\n🗑️ LIMPANDO CARRINHO COMPLETO")
            
            # Limpa o estado reativo
            carrinho_cliente.set([])
            
            # ← IMPORTANTE: Dispara trigger
            carrinho_cliente_trigger.set(carrinho_cliente_trigger() + 1)
            
            print(f"✅ Carrinho limpo!")
            
            ui.notification_show("🗑️ Carrinho limpo!", type="message", duration=2)
            
        except Exception as e:
            print(f"Erro limpar_carrinho_cliente: {e}")
            import traceback
            traceback.print_exc()
            ui.notification_show(f"❌ Erro ao limpar carrinho: {e}", type="error")
 
        
    @reactive.Effect
    @reactive.event(input.gerar_pix_cashback_id) # <<< ASSUMINDO ESTE TRIGGER
    def _monitor_gerar_pix_cashback():
        """Gera QR Code PIX para pagamento de cashback pendente"""
        try:
            cliente_id = None
            try:
                # Tenta obter o ID do cliente do input que disparou o evento
                cliente_id = input.gerar_pix_cashback_id()
            except Exception:
                print("Erro ao ler input.gerar_pix_cashback_id()")
                return

            if not cliente_id:
                return

            print(f"\n📲 GERAR QR PIX CASHBACK - DEBUG")
            print(f"{'='*60}")
            print(f"Cliente ID: {cliente_id}")

            if not supabase: # Verifica se supabase está disponível
                 print("Supabase não conectado.")
                 return

            # Busca dados do cliente e a chave PIX associada ao usuário
            cliente_result = supabase.table('clientes').select('*, usuarios!clientes_usuario_id_fkey(pix_chave)').eq('id', cliente_id).execute()

            if not cliente_result.data:
                ui.notification_show("❌ Cliente não encontrado!", type="error")
                return

            cliente = cliente_result.data[0]
            usuario = cliente.get('usuarios', {}) # Pega o objeto 'usuarios' aninhado
            pix_chave = usuario.get('pix_chave') if usuario else None # Pega a chave PIX de dentro de 'usuarios'

            if not pix_chave:
                ui.notification_show("❌ Cliente não possui chave PIX cadastrada!", type="error")
                return

            # Busca cashbacks pendentes
            cashback_result = supabase.table('cashback_pagamentos').select('valor').eq(
                'cliente_id', cliente_id
            ).eq('pago', False).execute()

            if not cashback_result.data:
                ui.notification_show("❌ Nenhum cashback pendente para gerar PIX!", type="warning")
                return

            total_cashback = sum([float(c.get('valor', 0) or 0) for c in cashback_result.data])

            if total_cashback <= 0: # Verifica se o valor é maior que zero
                ui.notification_show("❌ Valor de cashback pendente é zero ou inválido!", type="warning")
                return

            # Gera payload PIX (assume que a função existe)
            payload_pix = gerar_pix_payload(
                chave=pix_chave,
                valor=total_cashback,
                beneficiario=cliente['nome_completo'][:25] # Limita o nome
            )

            # Gera QR Code (assume que a função existe)
            qrcode_base64 = qrcode_base64 = gerar_qr_code(payload_pix)

            # Monta o HTML do Modal (com correções de estilo e fechamento)
            modal_html = f'''
            <div id="pix_modal_cashback_{cliente_id}" style="
                position: fixed; top: 0; left: 0; width: 100%; height: 100%;
                background: rgba(0,0,0,0.8); z-index: 9999;
                display: flex; align-items: center; justify-content: center;
            " onclick="this.remove()">
                <div style="
                    background: white; border-radius: 1rem; padding: 2rem;
                    max-width: 90%; width: 500px; text-align: center; box-shadow: 0 5px 15px rgba(0,0,0,0.3);
                " onclick="event.stopPropagation()">
                    <h3 style="color: #10b981; margin-bottom: 1rem;">💳 Pagamento de Cashback</h3>
                    <p style="color: #546E7A; margin-bottom: 1rem;">
                        Cliente: <strong>{cliente['nome_completo']}</strong><br>
                        Valor: <strong>{formatar_moeda(total_cashback)}</strong>
                    </p>

                    <img src="data:image/png;base64,{qrcode_base64}"
                         style="max-width: 80%; width: 300px; height: auto; border: 2px solid #e2e8f0; border-radius: 0.5rem; margin: 1rem auto; display: block;">

                    <div style="
                        background: #f1f5f9; padding: 1rem; border-radius: 0.5rem;
                        margin: 1rem 0; word-break: break-all; font-family: monospace; font-size: 0.75rem; text-align: left;
                    ">
                        {payload_pix}
                    </div>

                    <button id="copyBtn_{cliente_id}" onclick="
                        navigator.clipboard.writeText('{payload_pix}');
                        let btn = document.getElementById('copyBtn_{cliente_id}');
                        btn.innerText = '✅ Copiado!';
                        btn.style.background = '#059669'; /* Verde mais escuro */
                        setTimeout(() => {{
                            btn.innerText = '📋 Copiar Código PIX';
                            btn.style.background = '#10b981';
                        }}, 2000);
                    " style="
                        background: #10b981; color: white; border: none;
                        padding: 0.75rem 1.5rem; border-radius: 0.5rem;
                        font-weight: 600; cursor: pointer; width: 100%; margin-bottom: 0.5rem; transition: background 0.3s;
                    ">📋 Copiar Código PIX</button>

                    <button onclick="document.getElementById('pix_modal_cashback_{cliente_id}').remove()"
                        style="
                            background: #ef4444; color: white; border: none;
                            padding: 0.75rem 1.5rem; border-radius: 0.5rem;
                            font-weight: 600; cursor: pointer; width: 100%; transition: background 0.3s;
                        ">❌ Fechar</button>
                </div>
            </div>
            '''

            # Insere o modal no corpo da página
            ui.insert_ui(
                selector="body",
                where="beforeEnd",
                ui=ui.HTML(modal_html)
            )

            # Logs de sucesso
            print(f"✅ QR Code PIX gerado!")
            print(f"💰 Valor: {formatar_moeda(total_cashback)}")
            print(f"{'='*60}\n")

            # Notificação ao usuário (opcional, pois o modal já abre)
            # ui.notification_show(
            #     f"✅ QR Code PIX gerado!\n"
            #     f"💰 Valor: {formatar_moeda(total_cashback)}\n"
            #     f"👤 Beneficiário: {cliente['nome_completo']}",
            #     type="message",
            #     duration=8
            # )

        except Exception as e:
            print(f"❌ Erro em _monitor_gerar_pix_cashback: {e}")
            import traceback
            traceback.print_exc()
            ui.notification_show(f"❌ Erro ao gerar QR Code PIX: {str(e)}", type="error")


            
    def render_clinica_content(user):
        """Renderiza área da clínica"""
        
        # ========== LISTA DE ESPECIALIDADES MÉDICAS ==========
        especialidades = [
            "",
            "Acupuntura",
            "Alergia e Imunologia",
            "Anestesiologia",
            "Angiologia",
            "Cardiologia",
            "Cirurgia Cardiovascular",
            "Cirurgia da Mão",
            "Cirurgia de Cabeça e Pescoço",
            "Cirurgia do Aparelho Digestivo",
            "Cirurgia Geral",
            "Cirurgia Oncológica",
            "Cirurgia Pediátrica",
            "Cirurgia Plástica",
            "Cirurgia Torácica",
            "Cirurgia Vascular",
            "Clínica Médica",
            "Coloproctologia",
            "Dermatologia",
            "Endocrinologia e Metabologia",
            "Endoscopia",
            "Gastroenterologia",
            "Genética Médica",
            "Geriatria",
            "Ginecologia e Obstetrícia",
            "Hematologia e Hemoterapia",
            "Homeopatia",
            "Infectologia",
            "Mastologia",
            "Medicina de Emergência",
            "Medicina de Família e Comunidade",
            "Medicina do Trabalho",
            "Medicina de Tráfego",
            "Medicina Esportiva",
            "Medicina Física e Reabilitação",
            "Medicina Intensiva",
            "Medicina Legal",
            "Medicina Nuclear",
            "Medicina Preventiva e Social",
            "Nefrologia",
            "Neurocirurgia",
            "Neurologia",
            "Nutrologia",
            "Oftalmologia",
            "Oncologia Clínica",
            "Ortopedia e Traumatologia",
            "Otorrinolaringologia",
            "Patologia",
            "Patologia Clínica/Medicina Laboratorial",
            "Pediatria",
            "Pneumologia",
            "Psiquiatria",
            "Radiologia e Diagnóstico por Imagem",
            "Radioterapia",
            "Reumatologia",
            "Urologia"
        ]
        
        especialidades_dict = {e: e if e else "Selecione a especialidade" for e in especialidades}
        
        return ui.div(
            ui.h2("🏥 Área da Clínica"),
            ui.div(
                {"class": "card-custom"},
                ui.navset_pill(
                    # ========== NOVA ABA: ATENDIMENTO AO CLIENTE ==========
                    ui.nav_panel("🩺 Atendimento ao Cliente",
                        ui.div(
                            {"class": "card-custom", "style": "background: linear-gradient(135deg, #10b981, #059669); color: white; margin-bottom: 2rem; text-align: center; padding: 2rem;"},
                            ui.h3("🩺 Atendimento ao Cliente", style="margin: 0 0 0.5rem 0;"),
                            ui.p("Digite o código da venda para verificar se o cliente está apto ao atendimento", 
                                 style="margin: 0; opacity: 0.9;")
                        ),
                        
                        # Campo de busca
                        ui.row(
                            ui.column(8,
                                ui.input_text("codigo_venda", "Código da Venda", 
                                             placeholder="Ex: VND20251019XXXX")
                            ),
                            ui.column(4,
                                ui.input_action_button("btn_buscar_venda", "🔍 Buscar", 
                                                      class_="btn-primary w-100",
                                                      style="margin-top: 1.75rem;")
                            )
                        ),
                        
                        ui.hr(),
                        
                        # Resultado da busca
                        ui.output_ui("resultado_busca_venda")
                    ),
                    
                    # Aba: Cadastrar Procedimento                 
                    ui.nav_panel("🔬 Cadastrar Procedimento",
                        ui.h4("Novo Procedimento"),
                        ui.row(
                            ui.column(6, ui.input_text("proc_nome", "Nome do Procedimento*")),
                            ui.column(3, ui.output_ui("select_grupo")),
                            ui.column(3, ui.input_numeric("proc_preco", "Preço (R$)*", 0, min=0, step=0.01))
                        ),
                        ui.input_text_area("proc_descricao", "Descrição", rows=3),
                        ui.input_action_button("btn_add_proc", "➕ Cadastrar Procedimento", 
                                              class_="btn-primary mt-3"),
                        ui.hr(),
                        ui.h5("📤 Importar Planilha"),
                        ui.p("Envie um arquivo CSV ou Excel com as colunas: nome, grupo, preco"),
                        ui.input_file("upload_proc", "Selecionar Arquivo", accept=[".csv", ".xlsx"], 
                                     button_label="Escolher", multiple=False),
                        ui.input_action_button("btn_import_proc", "📥 Importar", class_="btn-primary mt-2"),
                        ui.hr(),
                        ui.h5("Procedimentos Cadastrados"),
                        ui.output_ui("tabela_procedimentos")
                    ),
                    
                    # Aba: Atendimentos Realizados
                    ui.nav_panel("📊 Atendimentos Realizados",
                        ui.div(
                            {"class": "card-custom", "style": "background: linear-gradient(135deg, #1DD1A1, #0D9488); color: white; margin-bottom: 2rem; text-align: center; padding: 2rem;"},
                            ui.h3("📊 Controle de Atendimentos", style="margin: 0 0 0.5rem 0;"),
                            ui.p("Acompanhe os atendimentos realizados e valores a receber", 
                                 style="margin: 0; opacity: 0.9;")
                        ),
                        
                        # Estatísticas
                        ui.row(
                            ui.column(4, ui.div({"class": "stat-card", "style": "background: linear-gradient(135deg, #10b981, #059669);"},
                                ui.div(ui.output_text("stat_atendimentos_realizados"), {"class": "stat-value"}),
                                ui.div("✅ Atendimentos", {"class": "stat-label"})
                            )),
                            ui.column(4, ui.div({"class": "stat-card", "style": "background: linear-gradient(135deg, #10b981, #059669);"},
                                ui.div(ui.output_text("stat_pagamentos_recebidos"), {"class": "stat-value"}),
                                ui.div("💰 Pagamentos Recebidos", {"class": "stat-label"})
                            )),
                            ui.column(4, ui.div({"class": "stat-card", "style": "background: linear-gradient(135deg, #10b981, #059669);"},
                                ui.div(ui.output_text("stat_valor_receber"), {"class": "stat-value"}),
                                ui.div("💵 A Receber", {"class": "stat-label"})
                            ))
                        ),
                        
                        ui.hr(),
                        
                        # Filtros
                        ui.row(
                            ui.column(6,
                                ui.input_select("filtro_status_atendimento", "Status do Pagamento",
                                    choices={
                                        "todos": "📋 Todos",
                                        "pendente": "⏳ Aguardando Pagamento",
                                        "pago": "✅ Pagamento Efetuado"
                                    })
                            ),
                            ui.column(6,
                                ui.input_text("buscar_atendimento", "Buscar por Código ou Cliente",
                                             placeholder="Digite para buscar...")
                            )
                        ),
                        
                        ui.hr(),
                        
                        # Lista de atendimentos

                        ui.output_ui("lista_atendimentos_realizados")
                    ),
                    
                    ui.nav_panel("🎁 Pacotes",
                        ui.h4("🎁 Criar e Gerenciar Pacotes"),
                        ui.p("Agrupe procedimentos existentes em um pacote com desconto."),
                        
                        # Formulário de Criação/Edição
                        ui.output_ui("pacote_form_ui"),
                        
                        # Resumo de Valores (Calculado dinamicamente)
                        ui.output_ui("pacote_resumo_valores"),
                        
                        # Botão Salvar/Atualizar
                        ui.output_ui("pacote_btn_salvar_ui"),
                        
                        ui.hr(style="margin: 2rem 0;"),
                        
                        # Lista de Pacotes Existentes
                        ui.h5("Pacotes Cadastrados"),
                        ui.output_ui("lista_pacotes_clinica")
                    ),
                    ui.nav_panel("📺 Minha Vitrine",
                        ui.h4("📺 Vitrine da Sala de Espera", style="color: #1e40af; margin-bottom: 1rem;"),
                        ui.p("Configure a página que seus clientes verão ao escanear o QR Code na sua recepção.", 
                             style="color: #64748b; margin-bottom: 2rem;"),
                        
                        # ========== CONFIGURAÇÕES GERAIS ==========
                        ui.div(
                            {"class": "card-custom", "style": "background: linear-gradient(135deg, #f0f9ff, #e0f2fe); border-left: 4px solid #3b82f6; margin-bottom: 1.5rem;"},
                            ui.h5("🎨 Configurações Gerais da Vitrine", style="color: #1e40af; margin-bottom: 1rem;"),
                            
                            ui.input_text("vitrine_titulo_input", "Título Principal*", 
                                          placeholder="Ex: Bem-vindo à Clínica Saúde Plus!"),
                            
                            ui.input_text_area("vitrine_mensagem_input", "Mensagem de Boas-Vindas*", rows=3,
                                               placeholder="Ex: Aproveite seu tempo de espera! Confira nossos pacotes promocionais de exames com desconto especial."),
                            
                            ui.input_file("vitrine_banner_input", "Banner Principal (Recomendado: 1200x400px)", 
                                          accept=[".png", ".jpg", ".jpeg", ".webp"],
                                          button_label="📸 Carregar Banner", multiple=False),
                            
                            ui.output_ui("vitrine_banner_preview"),
                            
                            ui.div(
                                {"style": "text-align: right; margin-top: 1rem;"},
                                ui.input_action_button("btn_salvar_vitrine_geral", "💾 Salvar Configurações Gerais", 
                                                      class_="btn-primary", 
                                                      style="background: linear-gradient(135deg, #3b82f6, #2563eb); border: none; padding: 0.75rem 2rem; font-weight: 600;")
                            )
                        ),
                        
                        ui.hr(style="margin: 2rem 0; border-top: 2px solid #e2e8f0;"),
                        
                        # ========== CONFIGURAÇÃO DOS PACOTES ==========
                        ui.div(
                            {"class": "card-custom", "style": "background: linear-gradient(135deg, #ecfdf5, #d1fae5); border-left: 4px solid #10b981; margin-bottom: 1.5rem;"},
                            ui.h5("🎁 Configurar Pacotes para Vitrine", style="color: #065f46; margin-bottom: 0.5rem;"),
                            ui.p("Personalize como cada pacote será exibido na vitrine (imagem, descrição motivacional, destaque).",
                                 style="color: #047857; font-size: 0.9rem; margin-bottom: 1.5rem;"),
                            
                            ui.output_ui("lista_pacotes_vitrine_config")
                        ),
                        
                        ui.hr(style="margin: 2rem 0; border-top: 2px solid #e2e8f0;"),
                        
                        # ========== QR CODE ==========
                        ui.div(
                            {"class": "card-custom", "style": "background: linear-gradient(135deg, #fef3c7, #fde68a); border-left: 4px solid #f59e0b;"},
                            ui.h5("📱 Seu QR Code da Vitrine", style="color: #92400e; margin-bottom: 0.5rem;"),
                            ui.p("Imprima e coloque na recepção e sala de espera para seus pacientes acessarem.", 
                                 style="color: #b45309; font-size: 0.9rem; margin-bottom: 1.5rem;"),
                            
                            ui.output_ui("vitrine_qr_code_display")
                        )
                    ),
                    # ========== NOVA ABA: CONFIGURAÇÕES ==========
                    ui.nav_panel("⚙️ Configurações",
                        ui.h4("⚙️ Configurações da Clínica"),
                        
                        # ========== DADOS CADASTRAIS ==========
                        ui.div(
                            {"class": "card-custom", "style": "margin-bottom: 1.5rem; background: linear-gradient(135deg, #dbeafe, #bfdbfe); border-left: 4px solid #3b82f6;"},
                            ui.h5("🏥 Dados da Clínica", style="margin-bottom: 1rem; color: #1e40af;"),
                            
                            ui.output_ui("form_editar_clinica"),
                            
                            ui.div(
                                {"style": "text-align: right; margin-top: 1rem;"},
                                ui.input_action_button("btn_salvar_dados_clinica", "💾 Salvar Alterações", 
                                                      class_="btn",
                                                      style="background: linear-gradient(135deg, #3b82f6, #2563eb); color: white; font-weight: 600; border: none; padding: 0.75rem 2rem;")
                            )
                        ),
                        
                        ui.hr(),
                        
                        # ========== GPS ==========
                        ui.div(
                            {"class": "card-custom", "style": "background: linear-gradient(135deg, #dcfce7, #bbf7d0); border-left: 4px solid #10b981;"},
                            ui.h5("📍 Localização GPS", style="margin-bottom: 1rem; color: #15803d;"),
                            ui.p("Seu GPS é calculado automaticamente com base no endereço acima. Atualize o endereço e clique no botão abaixo.", 
                                 style="color: #166534; margin-bottom: 1rem;"),
                            ui.div(
                                {"style": "background: white; padding: 1rem; border-radius: 0.5rem; margin-bottom: 1rem;"},
                                ui.output_text("status_gps_clinica")
                            ),
                            ui.input_action_button("btn_atualizar_gps", "🔄 Atualizar GPS Automaticamente", 
                                                  class_="btn",
                                                  style="background: linear-gradient(135deg, #10b981, #059669); color: white; font-weight: 600; border: none;")
                        )
                    )
                )
            )
        )

    def render_cliente_content(user):
        """Renderiza área do cliente"""
        return ui.div(
            ui.h2("👤 Área do Cliente"),
            
            # ========== CARDS DE NÍVEL DE CASHBACK ==========
            ui.div(
                {"class": "card-custom", "style": "background: linear-gradient(135deg, #10b981, #059669); color: white; margin-bottom: 1.5rem; padding: 1.5rem; box-shadow: 0 8px 16px rgba(16, 185, 129, 0.3);"},
                ui.row(
                    ui.column(6,
                        ui.h5(" Seu Nível de Cashback", style="margin: 0 0 1rem 0; color: white; font-weight: 700;"),
                        ui.output_ui("nivel_cashback_cliente")
                    ),
                    ui.column(6,
                        ui.h5("📈 Progresso para o Próximo Nível", style="margin: 0 0 1rem 0; color: white; font-weight: 700;"),
                        ui.output_ui("progresso_nivel")
                    )
                )
            ),
            
            ui.div(
                {"class": "card-custom mt-4"},
                ui.navset_pill(
                    ui.nav_panel("🛒 Comprar Procedimentos",

                        ui.HTML("""
                        <style>
                        .location-banner {
                            background: linear-gradient(135deg, #10b981, #059669);
                            color: white;
                            padding: 1.5rem;
                            border-radius: 0.75rem;
                            margin-bottom: 1.5rem;
                            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                            border: 3px solid #34d399;
                        }
                        
                        .location-banner h5 {
                            margin: 0 0 0.5rem 0;
                            font-size: 1.2rem;
                            font-weight: 600;
                        }
                        
                        .location-banner p {
                            margin: 0 0 1rem 0;
                            font-size: 0.95rem;
                            opacity: 0.95;
                            line-height: 1.4;
                        }
                        
                        .btn-location {
                            background: white;
                            color: #1DD1A1;
                            border: none;
                            padding: 0.7rem 1.5rem;
                            border-radius: 0.5rem;
                            font-weight: 600;
                            cursor: pointer;
                            margin-right: 0.75rem;
                            margin-bottom: 0.5rem;
                            transition: all 0.3s;
                            display: inline-block;
                        }
                        
                        .btn-location:hover {
                            transform: translateY(-2px);
                            box-shadow: 0 4px 8px rgba(0,0,0,0.2);
                        }
                        
                        .btn-location-secondary {
                            background: rgba(255,255,255,0.2);
                            color: white;
                            border: 2px solid white;
                        }
                        
                        .btn-location-secondary:hover {
                            background: rgba(255,255,255,0.3);
                        }
                        
                        .location-status {
                            display: inline-flex;
                            align-items: center;
                            gap: 0.5rem;
                            background: rgba(16, 185, 129, 0.3);
                            padding: 0.75rem 1.25rem;
                            border-radius: 0.75rem;
                            margin-top: 0.5rem;
                        }
                        
                        .location-denied {
                            background: rgba(239, 68, 68, 0.3);
                        }
                        
                        .location-icon {
                            font-size: 1.5rem;
                        }
                        
                        .filtros-cidade {
                            display: none;
                            background: rgba(255, 255, 255, 0.15);
                            padding: 1.25rem;
                            border-radius: 0.75rem;
                            margin-top: 1rem;
                        }
                        
                        .filtros-cidade.active {
                            display: block;
                        }
                        
                        .filtros-cidade label {
                            color: white;
                            font-weight: 600;
                            margin-bottom: 0.5rem;
                            display: block;
                            font-size: 0.95rem;
                        }
                        
                        .filtros-cidade select {
                            width: 100%;
                            padding: 0.65rem;
                            border-radius: 0.5rem;
                            border: 2px solid white;
                            background: white;
                            color: #2D3748;
                            font-size: 1rem;
                            font-weight: 500;
                            cursor: pointer;
                        }
                        
                        .filtros-cidade select:focus {
                            outline: none;
                            border-color: #10b981;
                            box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.3);
                        }
                        </style>
                        
                        <div id="locationBanner" class="location-banner">
                            <h5>📍 Encontre procedimentos perto de você!</h5>
                            <p>Escolha como deseja buscar: por GPS (mais preciso) ou por cidade específica.</p>
                            
                            <button class="btn-location" onclick="solicitarLocalizacao()">
                                ✨ Usar Minha Localização (GPS)
                            </button>
                            <button class="btn-location btn-location-secondary" onclick="mostrarFiltrosCidade()">
                                🏙️ Escolher Cidade
                            </button>
                            
                            <div id="locationStatus" style="display: none;"></div>
                            
                            <!-- FILTROS DE ESTADO E CIDADE -->
                            <div id="filtrosCidade" class="filtros-cidade">
                                <div style="display: grid; grid-template-columns: 1fr 2fr; gap: 1rem;">
                                    <div>
                                        <label for="filtro_estado">Estado:</label>
                                        <select id="filtro_estado" onchange="carregarCidades()">
                                            <option value="">Selecione...</option>
                                            <option value="AC">Acre</option>
                                            <option value="AL">Alagoas</option>
                                            <option value="AP">Amapá</option>
                                            <option value="AM">Amazonas</option>
                                            <option value="BA">Bahia</option>
                                            <option value="CE">Ceará</option>
                                            <option value="DF">Distrito Federal</option>
                                            <option value="ES">Espírito Santo</option>
                                            <option value="GO">Goiás</option>
                                            <option value="MA">Maranhão</option>
                                            <option value="MT">Mato Grosso</option>
                                            <option value="MS">Mato Grosso do Sul</option>
                                            <option value="MG">Minas Gerais</option>
                                            <option value="PA">Pará</option>
                                            <option value="PB">Paraíba</option>
                                            <option value="PR">Paraná</option>
                                            <option value="PE">Pernambuco</option>
                                            <option value="PI">Piauí</option>
                                            <option value="RJ">Rio de Janeiro</option>
                                            <option value="RN">Rio Grande do Norte</option>
                                            <option value="RS">Rio Grande do Sul</option>
                                            <option value="RO">Rondônia</option>
                                            <option value="RR">Roraima</option>
                                            <option value="SC">Santa Catarina</option>
                                            <option value="SP">São Paulo</option>
                                            <option value="SE">Sergipe</option>
                                            <option value="TO">Tocantins</option>
                                        </select>
                                    </div>
                                    <div>
                                        <label for="filtro_cidade">Cidade:</label>
                                        <select id="filtro_cidade" disabled>
                                            <option value="">Selecione um estado primeiro...</option>
                                        </select>
                                    </div>
                                </div>
                                
                                <button class="btn-location" style="margin-top: 1rem; width: 100%;" onclick="confirmarBuscaCidade()">
                                    ✅ Confirmar Localização
                                </button>
                            </div>
                        </div>
                        
                        <script>
                        let localizacaoAtiva = false;
                        let localizacaoNegada = false;
                        let cidadesSelecionadas = {
                            estado: '',
                            cidade: ''
                        };
                        
                        function solicitarLocalizacao() {
                            if (!navigator.geolocation) {
                                alert('❌ Seu navegador não suporta geolocalização');
                                mostrarFiltrosCidade();
                                return;
                            }
                            
                            const statusDiv = document.getElementById('locationStatus');
                            statusDiv.innerHTML = '<span style="color: white;">🔄 Obtendo sua localização...</span>';
                            statusDiv.style.display = 'block';
                            
                            // Oculta filtros se estiverem visíveis
                            document.getElementById('filtrosCidade').classList.remove('active');
                            
                            navigator.geolocation.getCurrentPosition(
                                function(position) {
                                    const lat = position.coords.latitude;
                                    const lon = position.coords.longitude;
                                    const accuracy = position.coords.accuracy;
                                    
                                    console.log('✅ Localização obtida:', lat, lon, 'Precisão:', accuracy, 'm');
                                    
                                    // Envia para o Shiny
                                    Shiny.setInputValue('geolocalizacao_cliente', {
                                        lat: lat,
                                        lon: lon,
                                        accuracy: accuracy,
                                        timestamp: new Date().getTime()
                                    }, {priority: 'event'});
                                    
                                    localizacaoAtiva = true;
                                    
                                    // Atualiza banner para estado de sucesso
                                    const banner = document.getElementById('locationBanner');
                                    banner.innerHTML = `
                                        <div class="location-status">
                                            <span class="location-icon">✅</span>
                                            <div>
                                                <strong style="font-size: 1.1rem;">Localização GPS Ativa</strong><br>
                                                <small style="opacity: 0.9;">Mostrando procedimentos próximos a você com distância em km</small>
                                            </div>
                                        </div>
                                    `;
                                    
                                    statusDiv.style.display = 'none';
                                },
                                function(error) {
                                    console.error('❌ Erro ao obter localização:', error);
                                    localizacaoNegada = true;
                                    
                                    let mensagemErro = '';
                                    let icone = '❌';
                                    
                                    switch(error.code) {
                                        case error.PERMISSION_DENIED:
                                            mensagemErro = 'Você negou o acesso à localização. Escolha uma cidade abaixo.';
                                            icone = '🏙️';
                                            break;
                                        case error.POSITION_UNAVAILABLE:
                                            mensagemErro = 'Localização indisponível. Escolha uma cidade abaixo.';
                                            icone = '⚠️';
                                            break;
                                        case error.TIMEOUT:
                                            mensagemErro = 'Tempo esgotado. Escolha uma cidade abaixo.';
                                            icone = '⏱️';
                                            break;
                                        default:
                                            mensagemErro = 'Erro ao obter localização. Escolha uma cidade abaixo.';
                                            icone = '❌';
                                    }
                                    
                                    statusDiv.innerHTML = `
                                        <div class="location-denied" style="padding: 1rem; border-radius: 0.5rem; margin-top: 0.5rem;">
                                            <span style="font-size: 1.2rem;">${icone}</span>
                                            <strong>${mensagemErro}</strong>
                                        </div>
                                    `;
                                    statusDiv.style.display = 'block';
                                    
                                    // Mostra filtros automaticamente
                                    setTimeout(() => {
                                        mostrarFiltrosCidade();
                                    }, 2000);
                                    
                                    // Notifica o Shiny
                                    Shiny.setInputValue('geolocalizacao_negada', {
                                        negada: true,
                                        motivo: error.code,
                                        timestamp: new Date().getTime()
                                    }, {priority: 'event'});
                                },
                                {
                                    enableHighAccuracy: true,
                                    timeout: 10000,
                                    maximumAge: 0
                                }
                            );
                        }
                        
                        function mostrarFiltrosCidade() {
                            console.log('🏙️ Mostrando filtros de cidade');
                            
                            // Mostra os filtros
                            const filtros = document.getElementById('filtrosCidade');
                            filtros.classList.add('active');
                            
                            // Oculta mensagem de status
                            document.getElementById('locationStatus').style.display = 'none';
                            
                            // Scroll suave até os filtros
                            filtros.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                        }
                        
                        function carregarCidades() {
                            const estado = document.getElementById('filtro_estado').value;
                            const selectCidade = document.getElementById('filtro_cidade');
                            
                            if (!estado) {
                                selectCidade.disabled = true;
                                selectCidade.innerHTML = '<option value="">Selecione um estado primeiro...</option>';
                                return;
                            }
                            
                            console.log('📍 Carregando cidades do estado:', estado);
                            
                            // Envia para o Shiny buscar as cidades
                            Shiny.setInputValue('buscar_cidades_estado', {
                                estado: estado,
                                timestamp: new Date().getTime()
                            }, {priority: 'event'});
                            
                            // Enquanto carrega...
                            selectCidade.disabled = true;
                            selectCidade.innerHTML = '<option value="">🔄 Carregando cidades...</option>';
                        }
                        
                        function confirmarBuscaCidade() {
                            const estado = document.getElementById('filtro_estado').value;
                            const cidade = document.getElementById('filtro_cidade').value;
                            
                            if (!estado || !cidade) {
                                alert('⚠️ Selecione um estado e uma cidade!');
                                return;
                            }
                            
                            console.log('✅ Cidade selecionada:', cidade, '/', estado);
                            
                            cidadesSelecionadas = { estado, cidade };
                            
                            // Envia para o Shiny
                            Shiny.setInputValue('cidade_selecionada_busca', {
                                estado: estado,
                                cidade: cidade,
                                timestamp: new Date().getTime()
                            }, {priority: 'event'});
                            
                            // Atualiza banner
                            const banner = document.getElementById('locationBanner');
                            banner.innerHTML = `
                                <div style="text-align: center; padding: 1rem;">
                                    <span style="font-size: 1.5rem;">🏙️</span>
                                    <strong style="display: block; margin-top: 0.5rem;">Buscando em ${cidade}/${estado}</strong>
                                    <small style="opacity: 0.85;">Clínicas nesta cidade serão priorizadas</small>
                                </div>
                            `;
                        }
                        </script>
                        """),

                        ui.row(
                            ui.column(10,
                                ui.input_text("buscar_procedimento_cliente", "🔍 Buscar Procedimento", 
                                             placeholder="Ex: Hemograma, Ultrassom, Raio-X...")
                            ),
                            ui.column(2,
                                ui.input_action_button("btn_buscar_proc_cliente", "🔍 Buscar", 
                                                      class_="btn-primary w-100",
                                                      style="margin-top: 1.75rem;")
                            )
                        ),
                        
                        ui.hr(),
                        ui.output_ui("resultado_busca_procedimentos")
                    ),  # Fecha ui.nav_panel "Comprar Procedimentos"
                    # ======================================================
                    # === CLINICA PARCEIRA - REDE MEDPIX ===
                    # ======================================================
                    ui.nav_panel("🏥 Rede MedPIX",
                        ui.h4("Explore Nossas Clínicas Parceiras"),
                        ui.p("Veja todos os procedimentos e pacotes oferecidos por uma clínica específica."),
                        
                        # Este output vai mostrar a LISTA de clínicas
                        # ou a PÁGINA de UMA clínica
                        ui.output_ui("view_clinicas_cliente")
                    ),
                    # ======================================================
                    # Aba 2: Carrinho
                    ui.nav_panel("🛒 Meu Carrinho",
                        ui.h4("Itens no Carrinho"),
                        ui.output_ui("carrinho_cliente_ui"),
                        ui.div(
                            {"style": "text-align: center; margin-top: 1rem;"},
                            ui.input_action_button(
                                "btn_limpar_carrinho_cliente",
                                "🗑️ Limpar Carrinho",
                                class_="btn btn-outline-danger",
                                style="font-weight: 600;"
                            )
                        ),
                        
                        # ============================================
                        # NOVA SEÇÃO: SELEÇÃO DE BENEFICIÁRIO
                        # ============================================
                        ui.div(
                            {"style": "margin-top: 2rem; margin-bottom: 2rem;"},
                            ui.card(
                                ui.card_header(
                                    ui.h5("👤 Para quem é este exame?", class_="mb-0")
                                ),
                                ui.card_body(
                                    # SELEÇÃO DO TIPO DE COMPRA
                                    ui.input_radio_buttons(
                                        "tipo_compra_cliente",
                                        None,
                                        choices={
                                            "proprio": "🙋 Para mim mesmo",
                                            "terceiro": "👥 Para outra pessoa (familiar, amigo, etc)",
                                            "presente": "🎁 É um presente"
                                        },
                                        selected="proprio"
                                    ),
                                    
                                    # DADOS DO BENEFICIÁRIO (aparece apenas se não for "proprio")
                                    ui.panel_conditional(
                                        "input.tipo_compra_cliente !== 'proprio'",
                                        ui.div(
                                            ui.tags.hr(),
                                            ui.h6("📋 Dados de quem vai usar o exame", class_="mb-3"),
                                            ui.p(
                                                "⚠️ Atenção: Estes dados aparecerão no código da venda e serão usados no atendimento da clínica.",
                                                class_="text-muted small mb-3"
                                            ),
                                            
                                            ui.row(
                                                ui.column(6,
                                                    ui.input_text(
                                                        "beneficiario_nome_cliente",
                                                        "Nome Completo *",
                                                        placeholder="Ex: Maria Silva Santos"
                                                    )
                                                ),
                                                ui.column(6,
                                                    ui.input_text(
                                                        "beneficiario_cpf_cliente",
                                                        "CPF *",
                                                        placeholder="000.000.000-00"
                                                    )
                                                )
                                            ),
                                            
                                            # Mensagem sobre o cashback
                                            ui.div(
                                                {"class": "alert alert-info mt-3", 
                                                 "style": "display: flex; align-items: center;"},
                                                ui.HTML('<i class="bi bi-info-circle me-2"></i>'),
                                                ui.span(
                                                    "💰 O cashback desta compra será creditado na sua conta, mesmo que o exame seja para outra pessoa.",
                                                    class_="small"
                                                )
                                            ),
                                            
                                            class_="mt-3"
                                        )
                                    )
                                )
                            )
                        ),
                        # ============================================
                        # FIM DA SEÇÃO BENEFICIÁRIO
                        # ============================================
                        
                        ui.div(
                            {"style": "text-align: right; margin-top: 2rem;"},
                            ui.h4(ui.output_text("total_carrinho_cliente"), 
                                 style="color: #1DD1A1; font-weight: bold;"),
                            ui.h5(ui.output_text("cashback_carrinho_cliente"), 
                                 style="color: #10b981; font-weight: bold;"),
                            ui.input_action_button("btn_finalizar_compra_cliente", "✅ Finalizar Compra", 
                                                  class_="btn-primary mt-3",
                                                  style="padding: 1rem 3rem; font-size: 1.1rem;")
                        )
                    ),  # Fecha ui.nav_panel "Meu Carrinho"
                    
                    # Aba 3: Minhas Compras
                    ui.nav_panel("📋 Minhas Compras",
                        ui.h4("Histórico de Compras"),
                        ui.output_ui("lista_minhas_compras_cliente")
                    ),  # Fecha ui.nav_panel "Minhas Compras"
                    
# ========== ABA 4: MEU CASHBACK ==========
                    ui.nav_panel("💰 Meu Cashback",
                        ui.h4("💰 Histórico de Cashback", style="margin-bottom: 1.5rem;"),
                        
                        # Botão de atualizar
                        ui.div(
                            {"style": "text-align: right; margin-bottom: 1rem;"},
                            ui.input_action_button(
                                "btn_atualizar_nivel",
                                "🔄 Atualizar",
                                class_="btn btn-sm btn-outline-secondary"
                            )
                        ),
                        
                        # ========== CARDS DE ESTATÍSTICAS ==========
                        ui.row(
                            ui.column(6, 
                                ui.div(
                                    {"class": "stat-card", "style": "background: linear-gradient(135deg, #10b981, #059669);"},
                                    ui.div(ui.output_text("stat_cashback_total_recebido"), {"class": "stat-value"}),
                                    ui.div("✅ Total Recebido", {"class": "stat-label"})
                                )
                            ),
                            ui.column(6, 
                                ui.div(
                                    {"class": "stat-card", "style": "background: linear-gradient(135deg, #f59e0b, #d97706);"},
                                    ui.div(ui.output_text("stat_cashback_aguardando"), {"class": "stat-value"}),
                                    ui.div("💰 Cashback Aguardando", {"class": "stat-label"})
                                ),
                                ui.output_ui("mensagem_status_cashback")
                            )
                        ),
                        
                        ui.hr(),
                        
                        # ========== LISTA DE CASHBACK ==========
                        ui.output_ui("lista_cashback_cliente")
                    ),  # Fecha ui.nav_panel "Meu Cashback"
                    id="tabs_cliente"
                )  # Fecha ui.navset_pill
            ),  # Fecha ui.div card-custom
            ui.output_ui("comprovante_upload_modal_ui")
        )  # Fecha ui.div principal
        
        
        
##################################
########## AREA OUTPUTS
##################################


    @reactive.Effect
    @reactive.event(input.buscar_cidades_estado)
    def _buscar_cidades_estado():
        """Busca cidades disponíveis no estado selecionado"""
        try:
            if not supabase:
                return
            
            dados = input.buscar_cidades_estado()
            estado = dados.get('estado')
            
            if not estado:
                return
            
            print(f"🔍 Buscando cidades no estado: {estado}")
            
            # Busca cidades distintas das clínicas no estado
            result = supabase.table('clinicas').select(
                'endereco_cidade'
            ).eq('endereco_estado', estado).execute()
            
            if not result.data:
                print(f"⚠️ Nenhuma clínica encontrada no estado {estado}")
                # Envia lista vazia
                ui.insert_ui(
                    ui.HTML("""
                    <script>
                    const selectCidade = document.getElementById('filtro_cidade');
                    selectCidade.disabled = true;
                    selectCidade.innerHTML = '<option value="">Nenhuma cidade disponível neste estado</option>';
                    </script>
                    """),
                    selector="body",
                    where="beforeEnd"
                )
                return
            
            # Remove duplicatas e ordena
            cidades = sorted(list(set([c['endereco_cidade'] for c in result.data if c.get('endereco_cidade')])))
            
            print(f"✅ Encontradas {len(cidades)} cidades em {estado}")
            
            # Monta HTML das options
            options_html = '<option value="">Selecione uma cidade...</option>'
            for cidade in cidades:
                options_html += f'<option value="{cidade}">{cidade}</option>'
            
            # Atualiza o select via JavaScript
            ui.insert_ui(
                ui.HTML(f"""
                <script>
                const selectCidade = document.getElementById('filtro_cidade');
                selectCidade.disabled = false;
                selectCidade.innerHTML = `{options_html}`;
                console.log('✅ {len(cidades)} cidades carregadas para {estado}');
                </script>
                """),
                selector="body",
                where="beforeEnd"
            )
            
        except Exception as e:
            print(f"❌ Erro ao buscar cidades: {e}")
            import traceback
            traceback.print_exc()


    @reactive.Effect
    @reactive.event(input.cidade_selecionada_busca)
    def _cidade_selecionada():
        """Quando usuário confirma cidade para busca"""
        try:
            dados = input.cidade_selecionada_busca()
            cidade = dados.get('cidade')
            estado = dados.get('estado')
            
            print(f"✅ Cidade selecionada para busca: {cidade}/{estado}")
            
            ui.notification_show(
                f"🏙️ Buscando em {cidade}/{estado}\n"
                f"Clínicas desta cidade serão priorizadas!",
                type="message",
                duration=5
            )
            
        except Exception as e:
            print(f"❌ Erro: {e}")

    # ========== ESTATÍSTICAS CLIENTE ==========
    @output
    @render.text
    def stat_minhas_compras():
        compras_trigger()  # <<< ADICIONA DEPENDÊNCIA DO GATILHO
        try:
            user = user_data()
            if not user or not supabase:
                return "0"
            # --- CORREÇÃO IMPORTANTE: Busca cliente_id ---
            cliente_result = supabase.table('clientes').select('id').eq('usuario_id', user['id']).maybe_single().execute()
            if not cliente_result.data:
                return "0"
            cliente_id = cliente_result.data['id']
            # ----------------------------------------------
            # Usa cliente_id na query
            result = supabase.table('vendas').select('id', count='exact').eq('cliente_id', cliente_id).execute() # <<< CORRIGIDO: Usa cliente_id
            return str(result.count or 0)
        except Exception as e: # Captura exceção específica
            print(f"Erro em stat_minhas_compras: {e}")
            return "0"

    @output
    @render.text
    def stat_meu_cashback():
        """Total de cashback JÁ recebido pelo cliente (APENAS de vendas confirmadas)"""
        cashback_trigger()
        try:
            user = user_data()
            if not user or not supabase:
                return "R$ 0,00"
            
            # Busca cliente_id
            cliente_result = supabase.table('clientes').select('id').eq('usuario_id', user['id']).maybe_single().execute()
            if not cliente_result.data:
                return "R$ 0,00"
            cliente_id = cliente_result.data['id']
            
            # Busca cashback PAGO COM JOIN na tabela vendas
            result = supabase.table('cashback_pagamentos').select(
                'valor, vendas!inner(pagamento_confirmado)'
            ).eq('cliente_id', cliente_id).eq('pago', True).execute()

            if not result.data:
                return "R$ 0,00"

            # ========== FILTRO CRÍTICO: Apenas vendas confirmadas ==========
            cashbacks_confirmados = [
                c for c in result.data 
                if c.get('vendas', {}).get('pagamento_confirmado', False)
            ]
            
            if not cashbacks_confirmados:
                return "R$ 0,00"

            total = sum([float(c.get('valor', 0) or 0) for c in cashbacks_confirmados])
            return formatar_moeda(total)
            
        except Exception as e:
            print(f"Erro em stat_meu_cashback: {e}")
            import traceback
            traceback.print_exc()
            return "R$ 0,00"


    @output
    @render.text
    def stat_cashback_pendente():
        """Total de cashback aguardando pagamento (APENAS de vendas confirmadas)"""
        cashback_trigger()
        try:
            user = user_data()
            if not user or not supabase:
                return "R$ 0,00"
            
            # Busca cliente_id
            cliente_result = supabase.table('clientes').select('id').eq('usuario_id', user['id']).maybe_single().execute()
            if not cliente_result.data:
                 return "R$ 0,00"
            cliente_id = cliente_result.data['id']
            
            # Busca cashback pendente COM JOIN na tabela vendas
            result = supabase.table('cashback_pagamentos').select(
                'valor, vendas!inner(pagamento_confirmado)'
            ).eq('cliente_id', cliente_id).eq('pago', False).execute()

            if not result.data:
                return "R$ 0,00"

            # ========== FILTRO CRÍTICO: Apenas vendas confirmadas ==========
            cashbacks_confirmados = [
                c for c in result.data 
                if c.get('vendas', {}).get('pagamento_confirmado', False)
            ]
            
            if not cashbacks_confirmados:
                return "R$ 0,00"

            total = sum([float(c.get('valor', 0) or 0) for c in cashbacks_confirmados])
            return formatar_moeda(total)
            
        except Exception as e:
            print(f"Erro em stat_cashback_pendente: {e}")
            import traceback
            traceback.print_exc()
            return "R$ 0,00"

    # ========== BUSCAR PROCEDIMENTOS ==========
    @reactive.Effect
    @reactive.event(input.buscar_procedimento)  # Ou o evento de busca que você usa
    def _realizar_busca_procedimentos():
        """Busca procedimentos usando geolocalização ou cidade"""
        try:
            termo_busca = input.termo_procedimento()  # Ajuste o nome do input
            
            if not termo_busca or len(termo_busca) < 3:
                ui.notification_show("Digite pelo menos 3 caracteres", type="warning")
                return
            
            user = user_data()
            if not user or not supabase:
                ui.notification_show("Faça login para buscar", type="error")
                return
            
            # Busca dados do cliente
            cliente_result = supabase.table('clientes').select('*').eq('usuario_id', user['id']).execute()
            
            if not cliente_result.data:
                ui.notification_show("Complete seu cadastro antes de buscar", type="warning")
                return
            
            cliente = cliente_result.data[0]
            
            # Tenta usar GPS primeiro
            cliente_lat = cliente.get('latitude')
            cliente_lon = cliente.get('longitude')
            usa_gps = cliente.get('usa_geolocalizacao', False)
            
            # Fallback: cidade/estado
            cidade = cliente.get('endereco_cidade')
            estado = cliente.get('endereco_estado')
            
            print(f"\n{'='*60}")
            print(f"🔍 INICIANDO BUSCA")
            print(f"{'='*60}")
            print(f"Termo: {termo_busca}")
            print(f"GPS disponível: {usa_gps and cliente_lat and cliente_lon}")
            print(f"Cidade: {cidade}/{estado}")
            
            # Realiza busca híbrida
            procedimentos = buscar_procedimentos_hibrido(
                termo_busca=termo_busca,
                cliente_lat=cliente_lat if usa_gps else None,
                cliente_lon=cliente_lon if usa_gps else None,
                cidade=cidade,
                estado=estado,
                raio_km=50
            )
            
            if not procedimentos:
                ui.notification_show(
                    f"😔 Nenhum procedimento encontrado para '{termo_busca}'",
                    type="warning",
                    duration=5
                )
                return
            
            # Monta mensagem de resultado
            modo = procedimentos[0].get('modo_busca', 'geral')
            
            if modo == 'gps':
                distancia_mais_proxima = procedimentos[0].get('distancia_km', 0)
                mensagem = f"✅ {len(procedimentos)} resultados encontrados!\n📍 O mais próximo está a {distancia_mais_proxima} km"
            elif modo == 'cidade':
                mesma_cidade = len([p for p in procedimentos if p.get('prioridade') == 1])
                if mesma_cidade > 0:
                    mensagem = f"✅ {mesma_cidade} resultados em {cidade}!\n📍 Total: {len(procedimentos)}"
                else:
                    mensagem = f"✅ {len(procedimentos)} resultados encontrados!\n🏙️ Nenhum em {cidade}, mostrando cidades próximas"
            else:
                mensagem = f"✅ {len(procedimentos)} resultados encontrados!"
            
            ui.notification_show(mensagem, type="message", duration=6)
            
            # Atualiza lista (ajuste conforme sua implementação)
            # procedimentos_encontrados.set(procedimentos)
            # trigger_atualizar_lista.set(trigger_atualizar_lista() + 1)
            
            print(f"✅ Busca concluída: {len(procedimentos)} resultados")
            print(f"{'='*60}\n")
            
        except Exception as e:
            print(f"❌ Erro na busca: {e}")
            import traceback
            traceback.print_exc()
            ui.notification_show(f"Erro ao buscar: {str(e)}", type="error")

    @output
    @render.ui
    def resultado_busca_procedimentos():
        procs = busca_procedimentos() # Agora contém procs E pacotes
        
        if not procs:
            return ui.div(
                {"style": "text-align: center; padding: 3rem; color: #94a3b8;"},
                ui.h5("🔍 Digite o nome do procedimento acima"),
                ui.p("Ex: Hemograma, Ultrassom, Raio-X, etc.")
            )
        
        # Agrupa por clínica
        clinicas_dict = {}
        for item in procs: # Renomeado de 'proc' para 'item'
            clinica = item.get('clinicas', {})
            clinica_id = clinica.get('id')
            
            if clinica_id not in clinicas_dict:
                clinicas_dict[clinica_id] = {
                    'info': clinica,
                    'itens': [], # Renomeado de 'procedimentos' para 'itens'
                    'distancia_km': item.get('distancia_km'),
                    'modo_busca': item.get('modo_busca', 'geral'),
                    'prioridade': item.get('prioridade', 3)
                }
            
            clinicas_dict[clinica_id]['itens'].append(item)
        
        cards = []
        for clinica_id, dados in clinicas_dict.items():
            clinica_info = dados['info']
            itens_da_clinica = dados['itens'] # Renomeado
            distancia = dados.get('distancia_km')
            modo_busca = dados.get('modo_busca', 'geral')
            prioridade = dados.get('prioridade', 3)
            
            nome_clinica = clinica_info.get('nome_fantasia') or clinica_info.get('razao_social', 'N/A')
            cidade = clinica_info.get('endereco_cidade', '')
            estado = clinica_info.get('endereco_estado', '')
            
            # --- (Lógica do badge_localizacao - IDÊNTICA A ANTES) ---
            badge_localizacao = ""
            if modo_busca == 'gps' and distancia is not None:
                if distancia < 1:
                    distancia_formatada = f"{int(distancia * 1000)} metros"
                elif distancia < 10:
                    distancia_formatada = f"{distancia:.1f} km"
                else:
                    distancia_formatada = f"{int(distancia)} km"
                badge_localizacao = f"""<div style="display: inline-block; background: linear-gradient(135deg, #10b981, #059669); color: white; padding: 0.5rem 1rem; border-radius: 1.5rem; font-size: 0.9rem; font-weight: 600; margin-bottom: 0.75rem; box-shadow: 0 2px 4px rgba(16, 185, 129, 0.3);">
                    📍 {distancia_formatada} de você
                </div>"""
            elif modo_busca == 'cidade':
                if prioridade == 1:
                    badge_localizacao = """<div style="display: inline-block; background: linear-gradient(135deg, #3b82f6, #2563eb); color: white; padding: 0.5rem 1rem; border-radius: 1.5rem; font-size: 0.9rem; font-weight: 600; margin-bottom: 0.75rem; box-shadow: 0 2px 4px rgba(59, 130, 246, 0.3);">
                        🏙️ Na sua cidade
                    </div>"""
                elif prioridade == 2:
                    badge_localizacao = """<div style="display: inline-block; background: linear-gradient(135deg, #8b5cf6, #7c3aed); color: white; padding: 0.5rem 1rem; border-radius: 1.5rem; font-size: 0.9rem; font-weight: 600; margin-bottom: 0.75rem; box-shadow: 0 2px 4px rgba(139, 92, 246, 0.3);">
                        📍 No seu estado
                    </div>"""
            # --- (FIM da lógica do badge) ---
            
            # --- (Lógica do cashback_perc - IDÊNTICA A ANTES) ---
            cashback_perc = 0
            try:
                # ... (código existente para buscar cashback) ...
                # (VAMOS RECALCULAR O CASHBACK NO CARRINHO, ENTÃO PODEMOS SIMPLIFICAR AQUI)
                # (Vamos usar o Nível do Cliente, não o da clínica)
                pass # Não precisa buscar o cashback da clínica aqui
            except:
                pass
            # --- (FIM da lógica do cashback) ---

            # ==========================================
            # === INÍCIO: GERAÇÃO DOS CARDS DE ITENS ===
            # ==========================================
            itens_html = []
            for item in itens_da_clinica:
                item_id_str = str(item['id'])
                item_tipo = item.get('tipo_item', 'procedimento')
                item_preco = float(item.get('preco', 0)) # 'preco' agora é 'preco' (proc) ou 'valor_final' (pacote)

                # Calcula cashback baseado no nível do cliente (igual ao do carrinho)
                user = user_data()
                cashback_perc_cliente = 4  # Padrão PRATA
                if user:
                    try:
                        cliente_id = cliente_logado.get()['id']
                        vendas_result = supabase.table('vendas').select('id', count='exact').eq('cliente_id', cliente_id).eq('pagamento_confirmado', True).execute()
                        total_compras = vendas_result.count if vendas_result.count else 0
                        
                        if total_compras >= 26: cashback_perc_cliente = 7
                        elif total_compras >= 11: cashback_perc_cliente = 5.5
                        else: cashback_perc_cliente = 4
                    except: pass
                
                cashback_calculado = item_preco * (cashback_perc_cliente / 100)

                
                if item_tipo == 'procedimento':
                    # --- Renderiza card de PROCEDIMENTO ---
                    item_html = ui.div(
                        {"style": "background: #f8fafc; padding: 1rem; border-radius: 0.5rem; margin-bottom: 0.5rem; border: 2px solid #e2e8f0;"},
                        ui.row(
                            ui.column(8,
                                ui.h6(f"🔬 {item.get('nome', 'N/A')}", style="margin: 0 0 0.5rem 0;"),
                                ui.p(f"💵 {formatar_moeda(item_preco)}", 
                                     style="margin: 0; font-weight: 600; color: #1DD1A1; font-size: 1rem;"),
                                ui.p(f"💰 Cashback: {formatar_moeda(cashback_calculado)}", 
                                     style="margin: 0.25rem 0 0 0; color: #10b981; font-size: 0.85rem;") if cashback_calculado > 0 else None
                            ),
                            ui.column(4,
                                ui.div(
                                    {"style": "text-align: right;"},
                                    ui.tags.button(
                                        "🛒 Adicionar",
                                        class_="btn btn-primary w-100",
                                        # ENVIA O TIPO JUNTO COM O ID
                                        onclick=f"Shiny.setInputValue('add_carrinho_cliente', 'procedimento:{item_id_str}', {{priority: 'event'}})",
                                        style="font-weight: 600;"
                                    )
                                )
                            )
                        )
                    )
                
                elif item_tipo == 'pacote':
                    # --- Renderiza card de PACOTE (NOVO) ---
                    nomes_sub_itens = item.get('nomes_sub_itens', [])
                    sub_itens_html = ", ".join(nomes_sub_itens)
                    if len(nomes_sub_itens) == 5:
                        sub_itens_html += "..."
                    
                    item_html = ui.div(
                        {"style": "background: linear-gradient(135deg, #f0f9ff, #e0f2fe); padding: 1rem; border-radius: 0.5rem; margin-bottom: 0.5rem; border: 2px solid #3b82f6;"},
                        ui.row(
                            ui.column(8,
                                ui.h6(f"🎁 {item.get('nome', 'N/A')}", style="margin: 0 0 0.5rem 0; color: #1e40af;"),
                                ui.p(
                                    f"💵 {formatar_moeda(item_preco)}", 
                                    style="margin: 0; font-weight: 700; color: #1d4ed8; font-size: 1.1rem;"
                                ),
                                # Mostra preço antigo se houver desconto
                                ui.p(
                                    f"(Valor base: {formatar_moeda(item.get('valor_base', 0))})",
                                    style="margin: 0.25rem 0; font-size: 0.85rem; color: #ef4444; text-decoration: line-through;"
                                ) if item.get('valor_desconto', 0) > 0 else None,
                                
                                ui.p(f"💰 Cashback: {formatar_moeda(cashback_calculado)}", 
                                     style="margin: 0.25rem 0 0 0; color: #10b981; font-size: 0.85rem;") if cashback_calculado > 0 else None,
                                
                                ui.p(
                                    f"Inclui: {sub_itens_html}",
                                    style="margin: 0.5rem 0 0 0; font-size: 0.8rem; color: #546E7A; font-style: italic;"
                                ) if sub_itens_html else None
                            ),
                            ui.column(4,
                                ui.div(
                                    {"style": "text-align: right;"},
                                    ui.tags.button(
                                        "🛒 Adicionar Pacote",
                                        class_="btn w-100",
                                        # ENVIA O TIPO JUNTO COM O ID
                                        onclick=f"Shiny.setInputValue('add_carrinho_cliente', 'pacote:{item_id_str}', {{priority: 'event'}})",
                                        style="font-weight: 600; background: #3b82f6; color: white;"
                                    )
                                )
                            )
                        )
                    )
                
                itens_html.append(item_html)
            # ==========================================
            # === FIM: GERAÇÃO DOS CARDS DE ITENS ===
            # ==========================================

            # Card da Clínica
            card = ui.div(
                {"class": "card-custom", "style": "margin-bottom: 1.5rem; border-left: 4px solid #1DD1A1;"},
                ui.row(
                    ui.column(12,
                        ui.HTML(badge_localizacao) if badge_localizacao else ui.div(),
                        
                        ui.div(
                            {"style": "display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;"},
                            ui.div(
                                ui.h5(f"🏥 {nome_clinica}", style="margin: 0; color: #2D3748;"),
                                ui.p(f"📍 {cidade}/{estado}", style="margin: 0.25rem 0 0 0; color: #546E7A; font-size: 0.9rem;")
                            ),
                            # Remove o cashback da clínica, pois o que vale é o do cliente
                        ),
                        
                        ui.hr(),
                        
                        ui.h6("🔬 Itens Disponíveis:", style="margin-bottom: 1rem;"),
                        
                        *itens_html # <-- INSERE OS CARDS GERADOS
                    )
                )
            )
            cards.append(card)
        
        return ui.div(*cards)

    # ========== ADICIONAR AO CARRINHO (CLIENTE) ==========
    @reactive.Effect
    @reactive.event(input.add_carrinho_cliente)
    def _monitor_add_carrinho_cliente():
        """Monitora quando cliente clica em adicionar ao carrinho (PROCEDIMENTO OU PACOTE)"""
        try:
            item_input = None
            try:
                item_input = input.add_carrinho_cliente()
            except Exception:
                return

            if not item_input or not supabase:
                return
            
            # --- NOVA LÓGICA DE PARSING ---
            if ":" not in item_input:
                print(f"❌ Erro no input do carrinho: {item_input} (sem tipo)")
                return
            
            tipo_item, item_id = item_input.split(":", 1)
            # --- FIM DA NOVA LÓGICA ---
            
            print(f"\n🛒 ADICIONANDO AO CARRINHO - DEBUG")
            print(f"Tipo: {tipo_item}, ID: {item_id}")

            # Busca percentual de cashback baseado no nível do cliente
            user = user_data()
            cashback_perc = 4  # Padrão PRATA
            
            if user:
                try:
                    cliente_id = cliente_logado.get()['id']
                    # Conta vendas confirmadas do cliente
                    vendas_result = supabase.table('vendas').select(
                        'id', count='exact'
                    ).eq('cliente_id', cliente_id).eq('pagamento_confirmado', True).execute()
                    
                    total_compras = vendas_result.count if vendas_result.count else 0
                    
                    # Define percentual baseado no nível
                    if total_compras >= 26:
                        cashback_perc = 7  # DIAMANTE
                    elif total_compras >= 11:
                        cashback_perc = 5.5  # OURO
                    
                    print(f"💎 Cliente com {total_compras} compras → {cashback_perc}% cashback")
                    
                except Exception as cb_err:
                    print(f"⚠️ Erro ao calcular cashback progressivo: {cb_err}")
                    cashback_perc = 4  # Usa padrão em caso de erro

            # Pega carrinho atual
            carrinho_atual = list(carrinho_cliente())
            
            # --- LÓGICA DE VERIFICAÇÃO DE ITEM EXISTENTE (MODIFICADA) ---
            cart_id_unico = f"{tipo_item}:{item_id}"
            
            item_existente_idx = None
            for idx, item in enumerate(carrinho_atual):
                if item.get('cart_id_unico') == cart_id_unico:
                    item_existente_idx = idx
                    break
            
            if item_existente_idx is not None:
                # --- Item já existe - incrementa quantidade ---
                carrinho_atual[item_existente_idx]['quantidade'] += 1
                # Recalcula cashback total para o item
                carrinho_atual[item_existente_idx]['cashback_valor_total'] = (
                    carrinho_atual[item_existente_idx]['preco_unitario'] *
                    carrinho_atual[item_existente_idx]['quantidade'] *
                    (carrinho_atual[item_existente_idx]['cashback_percentual'] / 100)
                )
                
                # Notificação de "Quantidade Atualizada"
                ui.notification_show(
                    ui.HTML(f"""
                    <div style="text-align: center;">
                        <div style="font-size: 2rem; margin-bottom: 0.5rem;">✅</div>
                        <h5 style="margin: 0 0 0.5rem 0; color: #2D3748;">Quantidade Atualizada!</h5>
                        <p style="margin: 0 0 1rem 0; color: #546E7A;">
                            🛒 {carrinho_atual[item_existente_idx]['quantidade']} unidade(s) no carrinho
                        </p>
                        <div style="display: flex; gap: 0.75rem; justify-content: center;">
                            <button onclick="let toast = this.closest('.shiny-notification'); if(toast) toast.remove();" 
                                    style="background: #f8fafc; color: #475569; border: 2px solid #cbd5e1; 
                                           padding: 0.6rem 1.25rem; border-radius: 0.5rem; font-weight: 600; 
                                           cursor: pointer;">
                                🔍 Adicionar Outro
                            </button>
                            <button onclick="Shiny.setInputValue('ir_para_carrinho', Math.random(), {{priority: 'event'}}); let toast = this.closest('.shiny-notification'); if(toast) toast.remove();"
                                    style="background: linear-gradient(135deg, #1DD1A1, #0D9488); color: white; 
                                           border: none; padding: 0.6rem 1.25rem; border-radius: 0.5rem; 
                                           font-weight: 600; cursor: pointer;">
                                🛒 Ir para Carrinho
                            </button>
                        </div>
                    </div>
                    """),
                    type="message",
                    duration=5
                )
            
            else:
                # --- Item novo - Busca dados no banco ---
                novo_item = None
                
                if tipo_item == 'procedimento':
                    result = supabase.table('procedimentos').select(
                        '*, clinicas(id, razao_social, nome_fantasia, whatsapp)'
                    ).eq('id', item_id).single().execute()
                    
                    if not result.data:
                        ui.notification_show("❌ Procedimento não encontrado!", type="error")
                        return
                    
                    proc = result.data
                    clinica = proc.get('clinicas', {})
                    preco_unit = float(proc.get('preco', 0))
                    
                    novo_item = {
                        'cart_id_unico': cart_id_unico,
                        'tipo_item': 'procedimento',
                        'item_id': item_id, # ID do procedimento
                        'clinica_id': clinica.get('id'),
                        'nome': proc.get('nome'),
                        'clinica_nome': clinica.get('nome_fantasia') or clinica.get('razao_social'),
                        'preco_unitario': preco_unit,
                        'quantidade': 1,
                        'cashback_percentual': cashback_perc,
                        'cashback_valor_total': preco_unit * (cashback_perc / 100),
                        'sub_itens': [] # Procedimento não tem sub-itens
                    }

                elif tipo_item == 'pacote':
                    result = supabase.table('pacotes').select(
                        '*, clinicas(id, razao_social, nome_fantasia, whatsapp), pacotes_itens(procedimentos(nome))'
                    ).eq('id', item_id).single().execute()
                    
                    if not result.data:
                        ui.notification_show("❌ Pacote não encontrado!", type="error")
                        return
                    
                    pacote = result.data
                    clinica = pacote.get('clinicas', {})
                    preco_unit = float(pacote.get('valor_final', 0))
                    
                    # Pega nomes dos sub-itens
                    nomes_sub_itens = [
                        item['procedimentos']['nome'] 
                        for item in pacote.get('pacotes_itens', []) 
                        if item.get('procedimentos')
                    ]
                    
                    novo_item = {
                        'cart_id_unico': cart_id_unico,
                        'tipo_item': 'pacote',
                        'item_id': item_id, # ID do pacote
                        'clinica_id': clinica.get('id'),
                        'nome': pacote.get('nome'),
                        'clinica_nome': clinica.get('nome_fantasia') or clinica.get('razao_social'),
                        'preco_unitario': preco_unit,
                        'quantidade': 1,
                        'cashback_percentual': cashback_perc,
                        'cashback_valor_total': preco_unit * (cashback_perc / 100),
                        'sub_itens': nomes_sub_itens
                    }
                
                if novo_item:
                    carrinho_atual.append(novo_item)
                    
                    # Notificação "Adicionado ao Carrinho"
                    ui.notification_show(
                        ui.HTML(f"""
                        <div style="text-align: center;">
                            <div style="font-size: 2rem; margin-bottom: 0.5rem;">✅</div>
                            <h5 style="margin: 0 0 0.5rem 0; color: #2D3748;">Adicionado ao Carrinho!</h5>
                            <p style="margin: 0 0 1rem 0; color: #10b981; font-weight: 600;">
                                💰 Cashback: {formatar_moeda(novo_item['cashback_valor_total'])}
                            </p>
                            <div style="display: flex; gap: 0.75rem; justify-content: center;">
                                <button onclick="let toast = this.closest('.shiny-notification'); if(toast) toast.remove();" 
                                        style="background: #f8fafc; color: #475569; border: 2px solid #cbd5e1; 
                                               padding: 0.6rem 1.25rem; border-radius: 0.5rem; font-weight: 600; 
                                               cursor: pointer;">
                                    🔍 Adicionar Outro
                                </button>
                                <button onclick="Shiny.setInputValue('ir_para_carrinho', Math.random(), {{priority: 'event'}}); let toast = this.closest('.shiny-notification'); if(toast) toast.remove();"
                                        style="background: linear-gradient(135deg, #1DD1A1, #0D9488); color: white; 
                                               border: none; padding: 0.6rem 1.25rem; border-radius: 0.5rem; 
                                               font-weight: 600; cursor: pointer;">
                                    🛒 Ir para Carrinho
                                </button>
                            </div>
                        </div>
                        """),
                        type="message",
                        duration=5
                    )
                
            # Atualiza o estado reativo
            carrinho_cliente.set(carrinho_atual)
            
            # Dispara trigger para forçar atualização da UI
            carrinho_cliente_trigger.set(carrinho_cliente_trigger() + 1)
            
            print(f"✅ Carrinho atualizado! Total de itens: {len(carrinho_atual)}")
            print(f"{'='*60}\n")

        except Exception as e:
            print(f"❌ Erro _monitor_add_carrinho_cliente: {e}")
            import traceback
            traceback.print_exc()
            ui.notification_show(f"❌ Erro ao adicionar item: {str(e)}", type="error")

# ========== NAVEGAR PARA CARRINHO ==========
    @reactive.Effect
    @reactive.event(input.ir_para_carrinho)
    def _navegar_para_carrinho():
        """Navega para a aba Meu Carrinho quando o botão é clicado"""
        try:
            ui.update_navset("tabs_cliente", selected="🛒 Meu Carrinho")
            print("✅ Navegado para aba Meu Carrinho")
        except Exception as e:
            print(f"❌ Erro ao navegar para carrinho: {e}")

    @output
    @render.ui
    def tabela_usuarios_avancada():
        try:
            print("\n🔍 Renderizando tabela_usuarios_avancada...")
            
            if not supabase:
                print("❌ Supabase não configurado")
                return ui.div(
                    {"class": "alert alert-warning"},
                    "⚠️ Banco de dados não configurado"
                )
            
            # Busca usuários
            query = supabase.table('usuarios').select('*')
            
            # Aplica filtros
            try:
                tipo_filtro = input.filtro_tipo_usuario_av()
                if tipo_filtro and tipo_filtro != "todos":
                    query = query.eq('tipo_usuario', tipo_filtro)
            except:
                pass
            
            try:
                busca = input.buscar_usuario_av()
                if busca:
                    # Busca por nome, email ou CPF
                    usuarios_all = supabase.table('usuarios').select('*').execute()
                    usuarios_filtrados = [
                        u for u in usuarios_all.data 
                        if busca.lower() in u.get('nome', '').lower() 
                        or busca.lower() in u.get('email', '').lower()
                        or busca in u.get('cpf', '')
                    ]
                    result = type('obj', (object,), {'data': usuarios_filtrados})()
                else:
                    result = query.order('nome').execute()
            except Exception as e:
                print(f"⚠️ Erro ao aplicar filtros: {e}")
                result = query.order('nome').execute()
            
            if not result.data:
                return ui.div(
                    {"style": "text-align: center; padding: 3rem; color: #94a3b8;"},
                    ui.h5("🔭 Nenhum usuário encontrado")
                )
            
            print(f"✅ {len(result.data)} usuários encontrados")
            
            cards = []
            for usuario in result.data:
                tipo_cor = {
                    "vendedor": "#f59e0b",
                    "clinica": "#06b6d4",
                    "superusuario": "#1DD1A1"
                }.get(usuario.get('tipo_usuario', ''), "#546E7A")
                
                status_cor = "#10b981" if usuario.get('ativo') else "#ef4444"
                
                # Calcula comissão
                comissao_info = "-"
                if usuario.get('tipo_usuario') == 'vendedor':
                    if usuario.get('comissao_percentual') and usuario.get('comissao_percentual') > 0:
                        comissao_info = f"{usuario['comissao_percentual']}%"
                    elif usuario.get('comissao_valor'):
                        comissao_info = formatar_moeda(usuario['comissao_valor'])
                
                card = ui.div(
                    {"class": "card-custom", "style": f"margin-bottom: 1rem; border-left: 4px solid {tipo_cor};"},
                    ui.row(
                        ui.column(9,
                            ui.div(
                                {"style": "display: flex; align-items: center; gap: 1rem; margin-bottom: 0.5rem;"},
                                ui.h6(usuario.get('nome', 'N/A'), style="margin: 0;"),
                                ui.span(
                                    usuario.get('tipo_usuario', 'N/A').title(),
                                    style=f"background: {tipo_cor}; color: white; padding: 0.25rem 0.75rem; border-radius: 1rem; font-size: 0.75rem; font-weight: 600;"
                                ),
                                ui.span(
                                    "✅ Ativo" if usuario.get('ativo') else "❌ Inativo",
                                    style=f"background: {status_cor}; color: white; padding: 0.25rem 0.75rem; border-radius: 1rem; font-size: 0.75rem; font-weight: 600;"
                                )
                            ),
                            ui.p(f"📧 {usuario.get('email', 'N/A')}", style="margin: 0.25rem 0; font-size: 0.9rem;"),
                            ui.p(f"📄 CPF: {formatar_cpf(usuario.get('cpf', ''))}", style="margin: 0.25rem 0; font-size: 0.9rem;"),
                            ui.p(f"💳 Comissão: {comissao_info}", style="margin: 0.25rem 0; font-size: 0.9rem; font-weight: 600; color: #1DD1A1;") if comissao_info != "-" else None,
                            ui.p(f"💰 PIX: {usuario.get('pix_chave', '❌ Não cadastrado')}", 
                                 style="margin: 0.25rem 0; font-size: 0.9rem; color: #10b981;") if usuario.get('tipo_usuario') == 'vendedor' else None
                        ),
                        ui.column(3,
                            ui.div(
                                {"style": "text-align: right;"},
                                ui.tags.button(
                                    "✏️ Editar",
                                    class_="btn btn-primary w-100 mb-2",
                                    onclick=f"Shiny.setInputValue('editar_usuario_id', '{usuario['id']}', {{priority: 'event'}})",
                                    style="font-size: 0.85rem; padding: 0.5rem;"
                                ),
                                ui.tags.button(
                                    "🔄 Ativar" if not usuario.get('ativo') else "⏸️ Desativar",
                                    class_=f"btn {'btn-success' if not usuario.get('ativo') else 'btn-warning'} w-100",
                                    onclick=f"Shiny.setInputValue('toggle_usuario_id', '{usuario['id']}', {{priority: 'event'}})",
                                    style="font-size: 0.85rem; padding: 0.5rem;"
                                )
                            )
                        )
                    )
                )
                cards.append(card)
            
            return ui.div(*cards)
            
        except Exception as e:
            print(f"❌ Erro em tabela_usuarios_avancada: {e}")
            import traceback
            traceback.print_exc()
            return ui.div(
                {"class": "alert alert-danger"},
                ui.h5("❌ Erro ao carregar usuários"),
                ui.p(str(e))
            )

# ========== TABELA CLÍNICAS AVANÇADA (CORRIGIDA) ==========
    @output
    @render.ui
    def tabela_clinicas_avancada():
        try:
            print("\n🔍 Renderizando tabela_clinicas_avancada...")
            
            if not supabase:
                return ui.div({"class": "alert alert-warning"}, "⚠️ Banco de dados não configurado")
            
            query = supabase.table('clinicas').select('*')
            
            # Aplica filtros
            try:
                status_filtro = input.filtro_status_clinica_av()
                if status_filtro and status_filtro == "ativo":
                    query = query.eq('ativo', True)
                elif status_filtro and status_filtro == "inativo":
                    query = query.eq('ativo', False)
            except:
                pass
            
            try:
                busca = input.buscar_clinica_av()
                if busca:
                    clinicas_all = supabase.table('clinicas').select('*').execute()
                    clinicas_filtradas = [
                        c for c in clinicas_all.data 
                        if busca.lower() in c.get('razao_social', '').lower() 
                        or busca.lower() in c.get('nome_fantasia', '').lower()
                        or busca in c.get('cnpj', '')
                        or busca.lower() in c.get('endereco_cidade', '').lower()
                    ]
                    result = type('obj', (object,), {'data': clinicas_filtradas})()
                else:
                    result = query.order('razao_social').execute()
            except:
                result = query.order('razao_social').execute()
            
            if not result.data:
                return ui.div(
                    {"style": "text-align: center; padding: 3rem; color: #94a3b8;"},
                    ui.h5("🔭 Nenhuma clínica encontrada")
                )
            
            print(f"✅ {len(result.data)} clínicas encontradas")
            
            cards = []
            for clinica in result.data:
                status_cor = "#10b981" if clinica.get('ativo') else "#ef4444"
                
                # Busca comissão
                comissao_info = "-"
                try:
                    comissao_result = supabase.table('comissoes_clinica').select('*').eq('clinica_id', clinica['id']).execute()
                    if comissao_result.data:
                        com = comissao_result.data[0]
                        if com.get('tipo') == 'percentual':
                            comissao_info = f"{com.get('valor_percentual', 0)}%"
                        else:
                            comissao_info = formatar_moeda(com.get('valor_fixo', 0))
                except:
                    pass
                
                card = ui.div(
                    {"class": "card-custom", "style": f"margin-bottom: 1rem; border-left: 4px solid {status_cor};"},
                    ui.row(
                        ui.column(9,
                            ui.div(
                                {"style": "display: flex; align-items: center; gap: 1rem; margin-bottom: 0.5rem;"},
                                ui.h6(clinica.get('razao_social', 'N/A'), style="margin: 0;"),
                                ui.span(
                                    "✅ Ativa" if clinica.get('ativo') else "❌ Inativa",
                                    style=f"background: {status_cor}; color: white; padding: 0.25rem 0.75rem; border-radius: 1rem; font-size: 0.75rem; font-weight: 600;"
                                )
                            ),
                            ui.p(f"🏢 {clinica.get('nome_fantasia', '-')}", style="margin: 0.25rem 0; font-size: 0.9rem;"),
                            ui.p(f"📄 CNPJ: {formatar_cnpj(clinica.get('cnpj', ''))}", style="margin: 0.25rem 0; font-size: 0.9rem;"),
                            ui.p(f"📍 {clinica.get('endereco_cidade', '-')}/{clinica.get('endereco_estado', '-')}", 
                                 style="margin: 0.25rem 0; font-size: 0.9rem;"),
                            ui.p(f"💳 Comissão: {comissao_info}", 
                                 style="margin: 0.25rem 0; font-size: 0.9rem; font-weight: 600; color: #1DD1A1;")
                        ),
                        ui.column(3,
                            ui.div(
                                {"style": "text-align: right;"},
                                ui.tags.button(
                                    "👁️ Ver",
                                    class_="btn btn-info w-100 mb-2",
                                    onclick=f"Shiny.setInputValue('ver_clinica_id', '{clinica['id']}', {{priority: 'event'}})",
                                    style="font-size: 0.85rem; padding: 0.5rem;"
                                ),
                                ui.tags.button(
                                    "🔄 Ativar" if not clinica.get('ativo') else "⏸️ Desativar",
                                    class_=f"btn {'btn-success' if not clinica.get('ativo') else 'btn-warning'} w-100",
                                    onclick=f"Shiny.setInputValue('toggle_clinica_id', '{clinica['id']}', {{priority: 'event'}})",
                                    style="font-size: 0.85rem; padding: 0.5rem;"
                                )
                            )
                        )
                    )
                )
                cards.append(card)
            
            return ui.div(*cards)
            
        except Exception as e:
            print(f"❌ Erro em tabela_clinicas_avancada: {e}")
            import traceback
            traceback.print_exc()
            return ui.div({"class": "alert alert-danger"}, ui.h5("❌ Erro"), ui.p(str(e)))
        
    # ========== TABELA CLIENTES AVANÇADA (CORRIGIDA) ==========
    @output
    @render.ui
    def tabela_clientes_avancada():
        try:
            print("\n🔍 Renderizando tabela_clientes_avancada...")
            
            if not supabase:
                return ui.div({"class": "alert alert-warning"}, "⚠️ Banco de dados não configurado")
            
            query = supabase.table('clientes').select('*, usuarios!clientes_usuario_id_fkey(pix_chave)')  # ✅ ADICIONA PIX
            
            # Aplica filtros
            try:
                status_filtro = input.filtro_status_cliente_av()
                if status_filtro and status_filtro == "ativo":
                    query = query.eq('ativo', True)
                elif status_filtro and status_filtro == "inativo":
                    query = query.eq('ativo', False)
            except:
                pass
            
            try:
                busca = input.buscar_cliente_av()
                if busca:
                    clientes_all = supabase.table('clientes').select('*').execute()
                    clientes_filtrados = [
                        c for c in clientes_all.data 
                        if busca.lower() in c.get('nome_completo', '').lower() 
                        or busca in c.get('cpf', '')
                    ]
                    result = type('obj', (object,), {'data': clientes_filtrados})()
                else:
                    result = query.order('nome_completo').limit(100).execute()
            except:
                result = query.order('nome_completo').limit(100).execute()
            
            if not result.data:
                return ui.div(
                    {"style": "text-align: center; padding: 3rem; color: #94a3b8;"},
                    ui.h5("🔭 Nenhum cliente encontrado")
                )
            
            print(f"✅ {len(result.data)} clientes encontrados")
            
            cards = []
            for cliente in result.data[:50]:
                status_cor = "#10b981" if cliente.get('ativo') else "#ef4444"
                
                # ✅ BUSCA PIX DO USUÁRIO
                pix_chave = "Não cadastrado"
                if cliente.get('usuarios'):
                    pix_chave = cliente['usuarios'].get('pix_chave', 'Não cadastrado')
                
                card = ui.div(
                    {"class": "card-custom", "style": f"margin-bottom: 1rem; border-left: 4px solid {status_cor}; padding: 1rem;"},
                    ui.row(
                        ui.column(9,
                            ui.h6(cliente.get('nome_completo', 'N/A'), style="margin: 0 0 0.5rem 0;"),
                            ui.p(f"📄 CPF: {formatar_cpf(cliente.get('cpf', ''))}", style="margin: 0.25rem 0; font-size: 0.9rem;"),
                            ui.p(f"📞 {cliente.get('telefone', '-')}", style="margin: 0.25rem 0; font-size: 0.9rem;"),
                            ui.p(f"🆔 Código: {cliente.get('codigo', '-')}", style="margin: 0.25rem 0; font-size: 0.9rem; color: #1DD1A1; font-weight: 600;"),
                            ui.p(f"💳 PIX: {pix_chave}", style="margin: 0.25rem 0; font-size: 0.9rem; color: #10b981; font-weight: 600;")  # ✅ ADICIONA PIX
                        ),
                        ui.column(3,
                            ui.div(
                                {"style": "text-align: right;"},
                                ui.span(
                                    "✅ Ativo" if cliente.get('ativo') else "❌ Inativo",
                                    style=f"background: {status_cor}; color: white; padding: 0.5rem 1rem; border-radius: 1rem; font-size: 0.85rem; font-weight: 600; display: inline-block;"
                                )
                            )
                        )
                    )
                )
                cards.append(card)
            
            if len(result.data) > 50:
                cards.append(
                    ui.div(
                        {"class": "alert alert-info", "style": "text-align: center;"},
                        f"ℹ️ Mostrando 50 de {len(result.data)} clientes. Use a busca para filtrar."
                    )
                )
            
            return ui.div(*cards)
            
        except Exception as e:
            print(f"❌ Erro em tabela_clientes_avancada: {e}")
            import traceback
            traceback.print_exc()
            return ui.div({"class": "alert alert-danger"}, ui.h5("❌ Erro"), ui.p(str(e)))
        
    # ========== TABELA VENDAS AVANÇADA (CORRIGIDA) ==========
    @output
    @render.ui
    def tabela_vendas_avancada():
        try:
            print("\n🔍 Renderizando tabela_vendas_avancada...")
            
            if not supabase:
                return ui.div({"class": "alert alert-warning"}, "⚠️ Banco de dados não configurado")
            
            query = supabase.table('vendas').select(
                '*, clientes(nome_completo), clinicas(razao_social), usuarios!vendas_vendedor_id_fkey(nome)'
            )
            
            # Aplica filtros
            try:
                tipo_filtro = input.filtro_tipo_venda_av()
                if tipo_filtro and tipo_filtro != "todos":
                    query = query.eq('tipo', tipo_filtro)
            except:
                pass
            
            try:
                status_filtro = input.filtro_status_venda_av()
                if status_filtro and status_filtro != "todos":
                    query = query.eq('status', status_filtro)
            except:
                pass
            
            try:
                busca = input.buscar_venda_av()
                if busca:
                    query = query.ilike('numero_venda', f'%{busca}%')
            except:
                pass
            
            result = query.order('criado_em', desc=True).limit(50).execute()
            
            if not result.data:
                return ui.div(
                    {"style": "text-align: center; padding: 3rem; color: #94a3b8;"},
                    ui.h5("🔭 Nenhuma venda encontrada")
                )
            
            print(f"✅ {len(result.data)} vendas encontradas")
            
            cards = []
            for venda in result.data:
                tipo_cor = "#1DD1A1" if venda.get('tipo') == 'venda' else "#f59e0b"
                
                cliente_nome = venda.get('clientes', {}).get('nome_completo', 'N/A') if venda.get('clientes') else 'N/A'
                clinica_nome = venda.get('clinicas', {}).get('razao_social', 'N/A') if venda.get('clinicas') else 'N/A'
                vendedor_data = venda.get('usuarios')
                vendedor_nome = vendedor_data.get('nome', 'N/A') if vendedor_data else 'N/A'
                data_criacao = pd.to_datetime(venda['criado_em']).strftime('%d/%m/%Y %H:%M')
                
                card = ui.div(
                    {"class": "card-custom", "style": f"margin-bottom: 1rem; border-left: 4px solid {tipo_cor}; padding: 1rem;"},
                    ui.row(
                        ui.column(9,
                            ui.div(
                                {"style": "display: flex; align-items: center; gap: 1rem; margin-bottom: 0.5rem;"},
                                ui.h6(f"📄 {venda['numero_venda']}", style="margin: 0;"),
                                ui.span(
                                    venda.get('tipo', 'N/A').title(),
                                    style=f"background: {tipo_cor}; color: white; padding: 0.25rem 0.75rem; border-radius: 1rem; font-size: 0.75rem; font-weight: 600;"
                                )
                            ),
                            ui.p(f"👤 Cliente: {cliente_nome}", style="margin: 0.25rem 0; font-size: 0.9rem;"),
                            ui.p(f"🏥 Clínica: {clinica_nome}", style="margin: 0.25rem 0; font-size: 0.9rem;"),
                            ui.p(f"💼 Vendedor: {vendedor_nome}", style="margin: 0.25rem 0; font-size: 0.9rem;"),
                            ui.p(f"💰 {formatar_moeda(venda.get('valor_total', 0))}", 
                                 style="margin: 0.25rem 0; font-size: 1rem; font-weight: 700; color: #1DD1A1;"),
                            ui.p(f"📅 {data_criacao}", style="margin: 0.25rem 0; font-size: 0.85rem; color: #546E7A;")
                        ),
                        ui.column(3,
                            ui.div(
                                {"style": "text-align: right;"},
                                ui.tags.button(
                                    "👁️ Detalhes",
                                    class_="btn btn-info w-100",
                                    onclick=f"Shiny.setInputValue('ver_detalhes_venda_id', '{venda['id']}', {{priority: 'event'}})",
                                    style="font-size: 0.85rem; padding: 0.5rem;"
                                )
                            )
                        )
                    )
                )
                cards.append(card)
            
            return ui.div(*cards)
            
        except Exception as e:
            print(f"❌ Erro em tabela_vendas_avancada: {e}")
            import traceback
            traceback.print_exc()
            return ui.div({"class": "alert alert-danger"}, ui.h5("❌ Erro"), ui.p(str(e)))

    # ========== 1. RENDERIZAR CARRINHO DO CLIENTE ==========
    @output
    @render.ui
    def carrinho_cliente_ui():
        """Exibe os itens do carrinho do cliente (PROCEDIMENTOS E PACOTES)"""
        try:
            carrinho_cliente_trigger()
            itens = list(carrinho_cliente())
            
            if not itens:
                return ui.div(
                    {"style": "text-align: center; padding: 3rem; color: #94a3b8;"},
                    ui.h5("🛒 Carrinho vazio"),
                    ui.p("Busque procedimentos e adicione ao carrinho")
                )
            
            cards = []
            for idx, item in enumerate(itens):
                # --- NOVO: Lógica para sub-itens de pacote ---
                sub_itens_html = None
                if item.get('tipo_item') == 'pacote' and item.get('sub_itens'):
                    sub_itens_lista = "".join(
                        f'<li style="font-size: 0.8rem; color: #546E7A;">{sub_nome}</li>' 
                        for sub_nome in item['sub_itens']
                    )
                    sub_itens_html = ui.div(
                        ui.p("Inclui:", style="margin: 0.5rem 0 0.25rem 0; font-size: 0.85rem; font-weight: 600;"),
                        ui.tags.ul(ui.HTML(sub_itens_lista), style="margin: 0; padding-left: 1.25rem;")
                    )
                
                # --- NOVO: Lógica de ícone e cor ---
                if item.get('tipo_item') == 'pacote':
                    item_nome = f"🎁 {item.get('nome')}"
                    card_style = "margin-bottom: 1rem; border-left: 4px solid #3b82f6; background: #f0f9ff;"
                else:
                    item_nome = f"🔬 {item.get('nome')}"
                    card_style = "margin-bottom: 1rem; border-left: 4px solid #1DD1A1;"
                
                card = ui.div(
                    {"class": "card-custom", "style": card_style},
                    ui.row(
                        ui.column(8,
                            ui.h6(item_nome, style="margin: 0 0 0.5rem 0;"),
                            ui.p(f"🏥 {item.get('clinica_nome')}", 
                                 style="margin: 0.25rem 0; font-size: 0.9rem; color: #546E7A;"),
                            ui.p(f"💵 {formatar_moeda(item.get('preco_unitario'))}", 
                                 style="margin: 0.25rem 0; font-weight: 600; color: #1DD1A1;"),
                            ui.p(f"📦 Quantidade: {item.get('quantidade', 1)}", 
                                 style="margin: 0.25rem 0; font-size: 0.9rem;"),
                            ui.p(f"💰 Cashback: {formatar_moeda(item.get('cashback_valor_total'))}", 
                                 style="margin: 0.25rem 0; color: #10b981; font-weight: 600;") if item.get('cashback_valor_total', 0) > 0 else None,
                            
                            sub_itens_html if sub_itens_html else ui.div() # <-- Adiciona sub-itens
                        ),
                        ui.column(4,
                            ui.div(
                                {"style": "text-align: right;"},
                                ui.tags.button(
                                    "🗑️ Remover",
                                    class_="btn btn-danger w-100",
                                    onclick=f"Shiny.setInputValue('remover_carrinho_cliente', '{idx}', {{priority: 'event'}})",
                                    style="font-weight: 600;"
                                )
                            )
                        )
                    )
                )
                cards.append(card)
            
            return ui.div(*cards)
            
        except Exception as e:
            print(f"Erro carrinho_cliente_ui: {e}")
            import traceback
            traceback.print_exc()
            return ui.div(ui.p(f"Erro: {str(e)}", style="color: red;"))


    # ========== 2.  ITEM DO CARRINHO ==========
    @reactive.Effect
    def _monitor__carrinho_cliente():
        """Remove item do carrinho do cliente"""
        try:
            idx = None
            try:
                idx = input._carrinho_cliente()
            except:
                return
            
            if idx is None:
                return
            
            idx = int(idx)
            carrinho_atual = carrinho_cliente()
            
            if 0 <= idx < len(carrinho_atual):
                item_removido = carrinho_atual.pop(idx)
                carrinho_cliente.set(carrinho_atual)
                
                ui.notification_show(
                    f"Item removido: {item_removido.get('nome')}",
                    type="message",
                    duration=3
                )
            
        except Exception as e:
            print(f"Erro _monitor__carrinho_cliente: {e}")


    # ========== 3. TOTAIS DO CARRINHO ==========
    @output
    @render.text
    def total_carrinho_cliente():
        try:
            carrinho_cliente_trigger()
            itens = list(carrinho_cliente())
            
            if not itens:
                return "Total: R$ 0,00"
            
            # --- LÓGICA ATUALIZADA ---
            total = sum([
                item.get('preco_unitario', 0) * item.get('quantidade', 1) 
                for item in itens
            ])
            return f"Total: {formatar_moeda(total)}"
        except:
            return "Total: R$ 0,00"


    @output
    @render.ui
    def nivel_cashback_cliente():
        """Mostra o nível atual de cashback do cliente (3 níveis)"""
        try:
            # Adiciona dependência do trigger para atualizar quando houver mudanças
            _ = cashback_trigger()
            _ = minhas_compras_trigger()
            
            if not supabase:
                return ui.div()
            
            user = user_data()
            if not user or user.get('tipo_usuario') != 'cliente':
                return ui.div()
            
# Primeiro busca o cliente_id da tabela clientes
            cliente_result = supabase.table('clientes').select('id').eq('usuario_id', user['id']).execute()
            
            if not cliente_result.data:
                print(f"⚠️ Cliente não encontrado para usuario_id: {user['id']}")
                total_compras = 0
            else:
                cliente_id = cliente_result.data[0]['id']
                print(f"🔍 cliente_id encontrado: {cliente_id}")
                
                # Agora busca vendas usando o cliente_id correto
                vendas_result = supabase.table('vendas').select(
                    'id', count='exact'
                ).eq('cliente_id', cliente_id).execute()
                
                total_compras = vendas_result.count if vendas_result.count else 0
            
            print(f"🔍 DEBUG nivel_cashback: total_compras = {total_compras}")
            
# Define informações do nível baseado APENAS em total_compras (3 níveis: PRATA, OURO, DIAMANTE)
            if total_compras >= 26:
                nivel_nome = "💎 DIAMANTE"
                percentual = 7
                cor_fundo = "linear-gradient(135deg, #9333ea, #7e22ce)"
                cor_badge = "#9333ea"
                proxima_meta = None
                compras_faltam = 0
            elif total_compras >= 11:
                nivel_nome = "🥇 OURO"
                percentual = 5.5
                cor_fundo = "linear-gradient(135deg, #eab308, #ca8a04)"
                cor_badge = "#eab308"
                proxima_meta = 26
                compras_faltam = 26 - total_compras
            else:
                nivel_nome = "🥈 PRATA"
                percentual = 4
                cor_fundo = "linear-gradient(135deg, #94a3b8, #546E7A)"
                cor_badge = "#546E7A"
                proxima_meta = 11
                compras_faltam = 11 - total_compras
            
            return ui.div(
                {"class": "card-custom", "style": f"background: {cor_fundo}; color: white; padding: 1.5rem; text-align: center;"},
                ui.div(
                    ui.h3(nivel_nome, style="margin: 0 0 0.5rem 0; font-weight: bold; font-size: 2rem;"),
                    ui.div(
                        {"style": "display: inline-block; background: rgba(255,255,255,0.2); padding: 0.5rem 1.5rem; border-radius: 2rem; margin: 0.5rem 0;"},
                        ui.h4(f"{percentual}% de Cashback", style="margin: 0; font-weight: 600;")
                    ),
                    ui.p(f"📊 Total de compras: {total_compras}", 
                         style="margin: 1rem 0 0.5rem 0; font-size: 1.1rem; opacity: 0.95;"),
                    ui.p(
                        f"🎯 Faltam {compras_faltam} compras para o próximo nível!" if proxima_meta else "🏆 Você alcançou o nível máximo!",
                        style="margin: 0; font-size: 0.95rem; opacity: 0.9;"
                    ) if proxima_meta or nivel == 3 else ui.div()
                )
            )
            
        except Exception as e:
            print(f"Erro em nivel_cashback_cliente: {e}")
            import traceback
            traceback.print_exc()
            return ui.div(
                {"class": "card-custom", "style": "background: #f1f5f9; padding: 1rem;"},
                ui.p("Erro ao carregar nível de cashback", style="color: #546E7A; text-align: center;")
            )


    @output
    @render.ui
    def progresso_nivel():
        """Mostra progresso para o próximo nível (3 níveis)"""
        try:
            # Adiciona dependência do trigger para atualizar quando houver mudanças
            _ = cashback_trigger()
            _ = minhas_compras_trigger()
            
            if not supabase:
                return ui.div()
            
            user = user_data()
            if not user or user.get('tipo_usuario') != 'cliente':
                return ui.div()
            
            # Primeiro busca o cliente_id da tabela clientes
            cliente_result = supabase.table('clientes').select('id').eq('usuario_id', user['id']).execute()
            
            if not cliente_result.data:
                print(f"⚠️ Cliente não encontrado para usuario_id: {user['id']}")
                total_compras = 0
            else:
                cliente_id = cliente_result.data[0]['id']
                
                # Agora busca vendas usando o cliente_id correto
                vendas_result = supabase.table('vendas').select(
                    'id', count='exact'
                ).eq('cliente_id', cliente_id).execute()
                
                total_compras = vendas_result.count if vendas_result.count else 0
            
            print(f"🔍 DEBUG progresso_nivel: total_compras = {total_compras}")
            
            # Define metas (3 níveis)
            if total_compras >= 26:
                # DIAMANTE - nível máximo
                return ui.div(
                    {"class": "card-custom", "style": "background: linear-gradient(135deg, #d1fae5, #a7f3d0); padding: 1.5rem; text-align: center;"},
                    ui.h5("🏆 Parabéns!", style="margin: 0 0 0.5rem 0; color: #047857;"),
                    ui.p("Você alcançou o nível máximo: DIAMANTE 💎", 
                         style="margin: 0; color: #065f46; font-weight: 600; font-size: 1.1rem;"),
                    ui.p(f"Continue comprando para acumular ainda mais cashback!", 
                         style="margin: 0.5rem 0 0 0; color: #047857; font-size: 0.9rem;")
                )
            
            elif total_compras >= 11:
                # OURO - próximo: DIAMANTE
                progresso = (total_compras - 11) / (26 - 11) * 100
                faltam = 26 - total_compras
                
                return ui.div(
                    {"class": "card-custom"},
                    ui.h6("📈 Progresso para DIAMANTE 💎", style="margin: 0 0 1rem 0; color: #047857;"),
                    ui.div(
                        {"style": "background: #d1fae5; border-radius: 1rem; height: 2rem; position: relative; overflow: hidden;"},
                        ui.div(
                            {"style": f"background: linear-gradient(90deg, #10b981, #059669); height: 100%; width: {progresso}%; transition: width 0.3s ease;"}
                        ),
                        ui.div(
                            {"style": "position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); font-weight: 600; color: #1f2937;"},
                            f"{total_compras}/26 compras"
                        )
                    ),
                    ui.p(f"🎯 Faltam apenas {faltam} {'compra' if faltam == 1 else 'compras'} para 7% de cashback!",
                         style="margin: 0.75rem 0 0 0; text-align: center; color: #047857; font-weight: 600;")
                )
            
            else:
                # PRATA - próximo: OURO
                progresso = (total_compras / 11) * 100
                faltam = 11 - total_compras
                
                return ui.div(
                    {"class": "card-custom"},
                    ui.h6("📈 Progresso para OURO 🥇", style="margin: 0 0 1rem 0; color: #059669;"),
                    ui.div(
                        {"style": "background: #d1fae5; border-radius: 1rem; height: 2rem; position: relative; overflow: hidden;"},
                        ui.div(
                            {"style": f"background: linear-gradient(90deg, #34d399, #10b981); height: 100%; width: {progresso}%; transition: width 0.3s ease;"}
                        ),
                        ui.div(
                            {"style": "position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); font-weight: 600; color: #1f2937;"},
                            f"{total_compras}/11 compras"
                        )
                    ),
                    ui.p(f"🎯 Faltam apenas {faltam} {'compra' if faltam == 1 else 'compras'} para 5,5% de cashback!",
                         style="margin: 0.75rem 0 0 0; text-align: center; color: #059669; font-weight: 600;")
                )
            
        except Exception as e:
            print(f"Erro em progresso_nivel: {e}")
            import traceback
            traceback.print_exc()
            return ui.div()

    @reactive.Effect
    @reactive.event(input.btn_atualizar_nivel)
    def atualizar_nivel_cliente_ui():
        """Força atualização dos cards de nível"""
        cashback_trigger.set(cashback_trigger() + 1)
        ui.notification_show("✅ Dados atualizados!", type="message", duration=2)

    @output
    @render.text
    def cashback_carrinho_cliente():
        try:
            carrinho_cliente_trigger()
            itens = list(carrinho_cliente())
            
            if not itens:
                return "Cashback: R$ 0,00"
            
            # --- LÓGICA ATUALIZADA ---
            # 'cashback_valor_total' já é o (preço_unitario * qtd * %)
            total_cashback = sum([
                item.get('cashback_valor_total', 0) 
                for item in itens
            ])
            return f"Você receberá de volta: {formatar_moeda(total_cashback)}"
        except:
            return "Cashback: R$ 0,00"

# ========== 2. REMOVER ITEM DO CARRINHO  ==========
    @reactive.Effect
    @reactive.event(input.remover_carrinho_cliente)  # <<< ADICIONADO o event decorator CORRETO
    def _monitor_remover_carrinho_cliente(): # <<< Nome opcionalmente alterado para clareza
        """Remove item do carrinho do cliente"""
        try:
            idx = None
            try:
                # Lê o índice enviado pelo botão clicado
                idx = input.remover_carrinho_cliente() # <<< CORRIGIDO o nome do input
            except Exception as e:
                # Se houver erro ao ler o input (raro, mas possível), apenas saia
                print(f"Aviso: Erro lendo input.remover_carrinho_cliente: {e}")
                return

            # Verifica se o índice foi realmente recebido
            if idx is None:
                print("Aviso: _monitor_remover_carrinho_cliente recebeu idx=None")
                return

            # Converte o índice para inteiro (vem como string do JS)
            idx = int(idx)

            # --- Cria uma CÓPIA da lista atual do carrinho ---
            # É importante trabalhar com uma cópia para evitar efeitos colaterais
            carrinho_atual = list(carrinho_cliente())
            # --------------------------------------------------

            print(f"\n🗑️ REMOVENDO ITEM - DEBUG") # Adiciona logs para depuração
            print(f"Índice recebido: {idx}")
            print(f"Carrinho ANTES ({len(carrinho_atual)} itens): {carrinho_atual}")


            # Verifica se o índice é válido para a lista atual
            if 0 <= idx < len(carrinho_atual):
                # Remove o item pelo índice
                item_removido = carrinho_atual.pop(idx)

                # Atualiza o valor reativo do carrinho com a nova lista (sem o item)
                carrinho_cliente.set(carrinho_atual)

                # --- DISPARA O TRIGGER para atualizar a UI ---
                # Isso força a re-renderização do carrinho e dos totais
                carrinho_cliente_trigger.set(carrinho_cliente_trigger() + 1)
                # ---------------------------------------------

                print(f"✅ Item removido: {item_removido.get('nome')}")
                print(f"Carrinho DEPOIS ({len(carrinho_atual)} itens): {carrinho_atual}")


                # Mostra notificação de sucesso
                ui.notification_show(
                    f"🗑️ Item removido: {item_removido.get('nome')}", # Adicionado emoji
                    type="message",
                    duration=3
                )
            else:
                 # Log caso o índice seja inválido (pode acontecer em casos raros)
                 print(f"❌ Índice inválido: {idx} (Tamanho do carrinho: {len(carrinho_atual)})")
                 ui.notification_show(f"⚠️ Erro: Índice {idx} inválido para remover item.", type="warning")


        except Exception as e:
            # Captura e exibe qualquer erro inesperado
            print(f"❌ Erro crítico em _monitor_remover_carrinho_cliente: {e}")
            import traceback
            traceback.print_exc()
            ui.notification_show(f"❌ Erro inesperado ao remover item: {str(e)}", type="error")
            

    @reactive.calc
    def dados_beneficiario_cliente():
        """Retorna os dados do beneficiário baseado na seleção"""
        tipo = input.tipo_compra_cliente()
        
        if tipo == "proprio":
            # Se for para si mesmo, usa os dados do cliente logado
            cliente_info = cliente_logado.get()
            if cliente_info:
                return {
                    "tipo_compra": "proprio",
                    "beneficiario_nome": cliente_info["nome_completo"],
                    "beneficiario_cpf": cliente_info["cpf"]
                }
        else:
            # Se for para terceiro ou presente, usa os dados informados
            return {
                "tipo_compra": tipo,
                "beneficiario_nome": input.beneficiario_nome_cliente() or "",
                "beneficiario_cpf": input.beneficiario_cpf_cliente() or ""
            }
        
        return None
    
    @reactive.calc
    def dados_beneficiario_cliente():
        """Retorna os dados do beneficiário baseado na seleção"""
        tipo = input.tipo_compra_cliente()
        
        if tipo == "proprio":
            # Se for para si mesmo, usa os dados do cliente logado
            cliente_info = cliente_logado.get()
            if cliente_info:
                return {
                    "tipo_compra": "proprio",
                    "beneficiario_nome": cliente_info["nome_completo"],
                    "beneficiario_cpf": cliente_info["cpf"]
                }
        else:
            # Se for para terceiro ou presente, usa os dados informados
            return {
                "tipo_compra": tipo,
                "beneficiario_nome": input.beneficiario_nome_cliente() or "",
                "beneficiario_cpf": input.beneficiario_cpf_cliente() or ""
            }
        
        return None
    
    @reactive.calc
    def validar_beneficiario_cliente():
        """Valida os dados do beneficiário"""
        dados = dados_beneficiario_cliente()
        
        if not dados:
            return {"valido": False, "erros": ["Dados do cliente não encontrados"]}
        
        erros = []
        
        if dados["tipo_compra"] != "proprio":
            # Validar nome completo
            nome = dados["beneficiario_nome"].strip()
            if not nome:
                erros.append("Nome completo é obrigatório")
            elif len(nome.split()) < 2:
                erros.append("Informe o nome completo (nome e sobrenome)")
            
            # Validar CPF
            cpf = dados["beneficiario_cpf"].strip()
            if not cpf:
                erros.append("CPF é obrigatório")
            else:
                # Remover formatação do CPF
                cpf_limpo = limpar_documento(cpf) # Usando sua função existente
                if len(cpf_limpo) != 11 or not cpf_limpo.isdigit():
                    erros.append("CPF inválido (deve ter 11 dígitos)")
                # (Você pode adicionar a validação de dígito verificador aqui se desejar)
        
        return {
            "valido": len(erros) == 0,
            "erros": erros
        }
    
    @reactive.calc
    def validar_beneficiario_cliente():
        """Valida os dados do beneficiário"""
        dados = dados_beneficiario_cliente()
        
        if not dados:
            return {"valido": False, "erros": ["Dados do cliente não encontrados"]}
        
        erros = []
        
        if dados["tipo_compra"] != "proprio":
            # Validar nome completo
            nome = dados["beneficiario_nome"].strip()
            if not nome:
                erros.append("Nome completo é obrigatório")
            elif len(nome.split()) < 2:
                erros.append("Informe o nome completo (nome e sobrenome)")
            
            # Validar CPF
            cpf = dados["beneficiario_cpf"].strip()
            if not cpf:
                erros.append("CPF é obrigatório")
            else:
                # Remover formatação do CPF
                cpf_limpo = cpf.replace(".", "").replace("-", "").replace(" ", "")
                if len(cpf_limpo) != 11 or not cpf_limpo.isdigit():
                    erros.append("CPF inválido (deve ter 11 dígitos)")
        
        return {
            "valido": len(erros) == 0,
            "erros": erros
        }

    # ========== 4. FINALIZAR COMPRA (CLIENTE) -  ==========

    @reactive.Effect
    @reactive.event(input.btn_finalizar_compra_cliente)
    def finalizar_compra_cliente():
        global PIX_COPIA_E_COLA_EMPRESA
        try:
            print("\n" + "="*60)
            print("FINALIZAR COMPRA CLIENTE (COM PACOTES) - DEBUG")
            print("="*60)

            user = user_data()
            if not user or not supabase:
                ui.notification_show("Usuario nao autenticado!", type="error")
                return

            itens = carrinho_cliente()
            if not itens:
                ui.notification_show("Carrinho vazio!", type="warning")
                return

            # ========== 1. VALIDAR BENEFICIÁRIO ==========
            validacao = validar_beneficiario_cliente()
            if not validacao["valido"]:
                ui.notification_show(
                    ui.HTML(f"""
                    <div style="text-align: left;">
                        <strong>❌ Erro nos dados do beneficiário:</strong><br>
                        {'<br>'.join(['• ' + erro for erro in validacao["erros"]])}
                    </div>
                    """),
                    type="error",
                    duration=7
                )
                return
            
            dados_benef = dados_beneficiario_cliente()
            print(f"👤 Beneficiário: {dados_benef['beneficiario_nome']} (Tipo: {dados_benef['tipo_compra']})")

            # ========== 2. BUSCAR DADOS DO CLIENTE (COMPRADOR) ==========
            cliente_result = supabase.table('clientes').select('*').eq('usuario_id', user['id']).execute()
            if not cliente_result.data:
                ui.notification_show("Dados do cliente nao encontrados!", type="error")
                return
            cliente = cliente_result.data[0]
            telefone_cliente = cliente.get('telefone', '')

            # ========== 3. AGRUPAR ITENS POR CLÍNICA ==========
            vendas_por_clinica = {}
            for item in itens:
                clinica_id = item.get('clinica_id')
                if clinica_id not in vendas_por_clinica:
                    vendas_por_clinica[clinica_id] = {
                        'itens_carrinho': [], # Lista de itens do carrinho
                        'total': 0,
                        'clinica_nome': item.get('clinica_nome', 'N/A')
                    }
                vendas_por_clinica[clinica_id]['itens_carrinho'].append(item)
                # O total da venda é a soma dos preços de carrinho (que já são os preços finais)
                vendas_por_clinica[clinica_id]['total'] += item.get('preco_unitario', 0) * item.get('quantidade', 1)

            print(f"Clinicas envolvidas: {len(vendas_por_clinica)}")

            vendas_criadas = []
            
            # ========== 4. CRIAR UMA VENDA PARA CADA CLÍNICA ==========
            for clinica_id, dados in vendas_por_clinica.items():
                
                # Gera número da venda com dados do beneficiário
                numero_venda = gerar_codigo_venda_com_beneficiario(
                    cliente_id=cliente['id'],
                    beneficiario_nome=dados_benef['beneficiario_nome'],
                    beneficiario_cpf=dados_benef['beneficiario_cpf'],
                    tipo_compra=dados_benef['tipo_compra']
                )
                
                total = dados['total']

                # Calcula cashback progressivo (baseado no total da venda daquela clínica)
                cashback_valor, percentual_cashback, nivel_cashback = calcular_cashback_progressivo(
                    cliente['id'],  
                    total
                )
                print(f"💰 Cashback para Clínica {clinica_id}: R$ {cashback_valor:.2f} ({percentual_cashback}% - Nível {nivel_cashback})")

                # Cria o registro da Venda principal
                venda_data = {
                    "numero_venda": numero_venda,
                    "tipo": "venda",
                    "cliente_id": cliente['id'],
                    "beneficiario_nome": dados_benef['beneficiario_nome'],
                    "beneficiario_cpf": limpar_documento(dados_benef['beneficiario_cpf']), # Salva CPF limpo
                    "tipo_compra": dados_benef['tipo_compra'],
                    "clinica_id": clinica_id,
                    "valor_total": total,
                    "status": "aguardando_pagamento",
                    "compra_online": True,
                    "pagamento_informado": False,
                    "pagamento_confirmado": False,
                    "criado_em": datetime.now(timezone.utc).isoformat(),
                    "expira_em": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat() # Expira em 1 hora
                }

                venda_result = supabase.table('vendas').insert(venda_data).execute()

                if not venda_result.data:
                    print(f"Erro ao criar venda para clinica {clinica_id}")
                    continue

                venda_id = venda_result.data[0]['id']

                # ======================================================
                # === INÍCIO: NOVA LÓGICA DE INSERÇÃO DE ITENS (CRÍTICO) ===
                # ======================================================
                itens_para_inserir_db = []
                
                for item_carrinho in dados['itens_carrinho']:
                    item_tipo = item_carrinho['tipo_item']
                    item_id_origem = item_carrinho['item_id'] # ID do proc ou pacote
                    quantidade = item_carrinho['quantidade']
                    
                    if item_tipo == 'procedimento':
                        # --- Caso 1: Procedimento Individual ---
                        print(f"   ... Adicionando Procedimento: {item_carrinho['nome']}")
                        itens_para_inserir_db.append({
                            "venda_id": venda_id,
                            "procedimento_id": item_id_origem,
                            "pacote_id": None, # É individual
                            "nome_procedimento": item_carrinho['nome'],
                            "quantidade": quantidade,
                            "preco_unitario": item_carrinho['preco_unitario'], # Preço real pago
                            "preco_total": item_carrinho['preco_unitario'] * quantidade
                        })
                        
                    elif item_tipo == 'pacote':
                        # --- Caso 2: Pacote (Explodir itens) ---
                        print(f"   ... Adicionando Pacote: {item_carrinho['nome']}")
                        
                        # Busca os sub-itens do pacote no DB
                        sub_itens_res = supabase.table('pacotes_itens').select(
                            'procedimento_id, valor_procedimento_na_epoca, procedimentos(nome)'
                        ).eq('pacote_id', item_id_origem).execute()
                        
                        if not sub_itens_res.data:
                            print(f"⚠️ Pacote {item_id_origem} não tem sub-itens! Pulando.")
                            continue
                            
                        # Calcula o "rateio" do preço pago pelo pacote entre os itens
                        # (Isso é importante se o pacote tem desconto)
                        valor_base_pacote = sum(float(si['valor_procedimento_na_epoca']) for si in sub_itens_res.data)
                        valor_final_pacote = item_carrinho['preco_unitario'] # Preço com desconto
                        
                        fator_desconto = 1.0 # Padrão
                        if valor_base_pacote > 0 and valor_final_pacote < valor_base_pacote:
                             fator_desconto = valor_final_pacote / valor_base_pacote
                        
                        print(f"      ... Fator Desconto Pacote: {fator_desconto:.4f} (Pago: {valor_final_pacote} / Base: {valor_base_pacote})")

                        for sub_item in sub_itens_res.data:
                            proc_id = sub_item['procedimento_id']
                            proc_nome = sub_item['procedimentos']['nome'] if sub_item.get('procedimentos') else 'Procedimento'
                            proc_preco_base = float(sub_item['valor_procedimento_na_epoca'])
                            
                            # Aplica o rateio do desconto ao preço do sub-item
                            proc_preco_pago = proc_preco_base * fator_desconto
                            
                            print(f"      ... Sub-item: {proc_nome} (Preço Rateado: {formatar_moeda(proc_preco_pago)})")
                            
                            itens_para_inserir_db.append({
                                "venda_id": venda_id,
                                "procedimento_id": proc_id,
                                "pacote_id": item_id_origem, # <-- VINCULA AO PACOTE
                                "nome_procedimento": proc_nome,
                                "quantidade": quantidade, # Quantidade do pacote
                                "preco_unitario": proc_preco_pago, # Preço rateado com desconto
                                "preco_total": proc_preco_pago * quantidade
                            })
                
                # Insere todos os itens da venda (procs e pacotes explodidos)
                if itens_para_inserir_db:
                    supabase.table('itens_venda').insert(itens_para_inserir_db).execute()
                # ====================================================
                # === FIM: NOVA LÓGICA DE INSERÇÃO DE ITENS ===
                # ====================================================

                # Cria registro de cashback (sempre para o COMPRADOR)
                if cashback_valor > 0:
                    cashback_data = {
                        "cliente_id": cliente['id'],
                        "venda_id": venda_id,
                        "valor": cashback_valor,
                        "percentual": percentual_cashback,
                        "pix_destino": user.get('pix_chave'),
                        "pago": False,
                        "nivel": nivel_cashback # Salva o nível do cliente na época
                    }
                    print(f"💾 Inserindo cashback: {cashback_data}")
                    supabase.table('cashback_pagamentos').insert(cashback_data).execute()

                vendas_criadas.append({
                    'numero': numero_venda,
                    'total': total,
                    'cashback': cashback_valor,
                    'clinica_nome': dados['clinica_nome']
                })
                print(f"Venda criada: {numero_venda} - {formatar_moeda(total)}")

            # ========== 5. ATUALIZAR CONTADOR DE COMPRAS (UMA VEZ) ==========
            try:
                cliente_db = supabase.table('usuarios').select('total_compras').eq('id', user['id']).execute()
                total_compras_atual = cliente_db.data[0].get('total_compras', 0) if cliente_db.data else 0
                
                # Incrementa em 1, não importa quantos pacotes/itens
                supabase.table('usuarios').update({
                    'total_compras': total_compras_atual + 1
                }).eq('id', user['id']).execute()
                
                # Re-calcula o nível do cliente
                atualizar_nivel_cliente(user['id'])
                
                print(f"✅ Total de compras atualizado: {total_compras_atual + 1}")
            except Exception as e:
                print(f"⚠️ Erro ao atualizar contador: {e}")

            if not vendas_criadas:
                ui.notification_show("Erro ao criar vendas!", type="error")
                return

            # ========== 6. MOSTRAR MODAL DE PAGAMENTO PIX ==========
            total_geral = sum([v['total'] for v in vendas_criadas])
            cashback_geral = sum([v['cashback'] for v in vendas_criadas])

            detalhes_vendas_modal = ""
            for v in vendas_criadas:
                detalhes_vendas_modal += f"<p style='margin: 0.25rem 0; font-size: 0.9rem;'><b>{v['clinica_nome']}</b>: {v['numero']} ({formatar_moeda(v['total'])})</p>"

            info_beneficiario = ""
            if dados_benef['tipo_compra'] == 'presente':
                info_beneficiario = f"""
                <div style="background: #fef3c7; padding: 0.75rem; border-radius: 0.5rem; margin: 1rem 0; text-align: left;">
                    <p style="margin: 0; font-size: 0.9rem; color: #92400e;">
                        🎁 <strong>Presente para:</strong> {dados_benef['beneficiario_nome']}<br>
                        CPF: {formatar_cpf_cnpj(dados_benef['beneficiario_cpf'])}
                    </p>
                </div>
                """
            elif dados_benef['tipo_compra'] == 'terceiro':
                info_beneficiario = f"""
                <div style="background: #dbeafe; padding: 0.75rem; border-radius: 0.5rem; margin: 1rem 0; text-align: left;">
                    <p style="margin: 0; font-size: 0.9rem; color: #1e40af;">
                        👥 <strong>Exame para:</strong> {dados_benef['beneficiario_nome']}<br>
                        CPF: {formatar_cpf_cnpj(dados_benef['beneficiario_cpf'])}
                    </p>
                </div>
                """

            pix_code_id = f"pixCode_{int(time.time())}"
            
            # --- Gera o payload do PIX com o VALOR TOTAL
            pix_payload_empresa = gerar_pix_payload(
                chave=limpar_documento(PIX_COPIA_E_COLA_EMPRESA[50:64]), # Extrai chave do pix global
                valor=total_geral,
                beneficiario="MedPIX", # Nome da sua empresa
                cidade="SAO PAULO", # Cidade da sua empresa
                txid=f"MEDPIX{int(time.time())}"
            )

            modal_html = f'''
            <div id="pix_payment_modal" style="
                position: fixed; top: 0; left: 0; width: 100%; height: 100%;
                background: rgba(0,0,0,0.8); z-index: 10000;
                display: flex; align-items: center; justify-content: center;
                overflow-y: auto; padding: 1rem;
            ">
                <div style="
                    background: white; border-radius: 1rem; padding: 2rem;
                    max-width: 95%; width: 550px;
                    text-align: center; box-shadow: 0 5px 15px rgba(0,0,0,0.3);
                ">
                    <h3 style="color: #10b981; margin-bottom: 1rem;">💳 Pagar com PIX</h3>
                    <p style="color: #546E7A; margin-bottom: 1.5rem;">
                        Copie o código abaixo e cole no seu aplicativo do banco para pagar.
                    </p>

                    <div style="margin-bottom: 1rem;">
                        <h5 style="margin: 0 0 0.5rem 0;">Resumo da Compra:</h5>
                        {detalhes_vendas_modal}
                        {info_beneficiario}
                        <hr style="margin: 0.5rem 0;">
                        <p style="margin: 0.5rem 0; font-size: 1.1rem;"><b>Valor Total: {formatar_moeda(total_geral)}</b></p>
                        <p style="margin: 0.25rem 0; font-size: 0.9rem; color: #10b981;">💰 Seu cashback: {formatar_moeda(cashback_geral)}</p>
                    </div>

                    <div style="
                        background: #f1f5f9; padding: 1rem; border-radius: 0.5rem;
                        margin: 1.5rem 0; word-break: break-all; font-family: monospace;
                        font-size: 0.8rem;
                        text-align: left; max-height: 100px; overflow-y: auto;
                    " id="{pix_code_id}">
                        {pix_payload_empresa}
                    </div>

                    <button id="copyPixBtn" onclick="
                        const textToCopy = document.getElementById('{pix_code_id}').innerText;
                        navigator.clipboard.writeText(textToCopy).then(() => {{
                            let btn = document.getElementById('copyPixBtn');
                            btn.innerText = '✅ Copiado!';
                            btn.style.background = '#059669';
                            setTimeout(() => {{
                                btn.innerText = 'Copiar Código PIX';
                                btn.style.background = '#10b981';
                            }}, 2500);
                        }}).catch(err => {{
                            console.error('Erro ao copiar:', err);
                            alert('Erro ao copiar o código. Tente selecionar e copiar manualmente.');
                        }});
                    " style="
                        background: #10b981; color: white; border: none;
                        padding: 0.75rem 1.5rem; border-radius: 0.5rem;
                        font-weight: 600; cursor: pointer; width: 100%; margin-bottom: 1rem;
                        transition: background 0.3s; font-size: 1rem;
                    ">Copiar Código PIX</button>

                    <button onclick="document.getElementById('pix_payment_modal').remove(); Shiny.setInputValue('mudar_aba_minhas_compras', Math.random(), {{priority: 'event'}});" style="
                        background: #546E7A; color: white; border: none;
                        padding: 0.6rem 1.5rem; border-radius: 0.5rem;
                        font-weight: 500; cursor: pointer; width: 100%;
                        transition: background 0.3s; font-size: 0.9rem;
                    ">Fechar (Pagarei Depois)</button>
                     <p style="font-size: 0.8rem; color: #546E7A; margin-top: 1rem;">
                        ⚠️ Após pagar, clique em 'Informar Pagamento' em 'Minhas Compras'.
                     </p>
                </div>
            </div>
            '''

            ui.insert_ui(
                selector="body",
                where="beforeEnd",
                ui=ui.HTML(modal_html)
            )
            print("✅ Modal PIX exibido!")

            # ========== 7. ENVIAR EMAIL DE CONFIRMAÇÃO DE PEDIDO ==========
            try:
                cliente_email = cliente.get('email')
                if cliente_email and '@' in cliente_email:
                    # (O seu código de envio de email existente)
                    # ... (ele não precisa de modificação, pois já itera sobre 'vendas_criadas')
                    info_beneficiario_email = ""
                    if dados_benef['tipo_compra'] == 'presente':
                        info_beneficiario_email = f"""
                        <div style="background-color: #fef3c7; border-left: 4px solid #f59e0b; padding: 15px; margin: 20px 0; border-radius: 5px;">
                            <p style="margin: 0; font-size: 16px; color: #92400e;">
                                🎁 <strong>Este é um presente para:</strong><br>
                                <strong>{dados_benef['beneficiario_nome']}</strong><br>
                                CPF: {formatar_cpf_cnpj(dados_benef['beneficiario_cpf'])}
                            </p>
                        </div>
                        """
                    elif dados_benef['tipo_compra'] == 'terceiro':
                         info_beneficiario_email = f"""
                        <div style="background-color: #dbeafe; border-left: 4px solid #3b82f6; padding: 15px; margin: 20px 0; border-radius: 5px;">
                            <p style="margin: 0; font-size: 16px; color: #1e40af;">
                                👥 <strong>Exame para:</strong><br>
                                <strong>{dados_benef['beneficiario_nome']}</strong><br>
                                CPF: {formatar_cpf_cnpj(dados_benef['beneficiario_cpf'])}
                            </p>
                        </div>
                        """
                    
                    lista_procedimentos = ""
                    for idx, v in enumerate(vendas_criadas):
                        clinica_nome = v['clinica_nome']
                        numero_venda = v['numero']
                        valor = formatar_moeda(v['total'])
                        lista_procedimentos += f"<li style='margin-bottom: 0.5rem;'><strong>{clinica_nome}</strong> - {numero_venda}<br>Valor: {valor}</li>"
                    
                    conteudo_email = f"""
                    <h2 style="color: #1DD1A1; margin-top: 0;">🎉 Pedido Realizado com Sucesso!</h2>
                    <p style="font-size: 16px; color: #374151; line-height: 1.6;">
                        Olá <strong>{cliente.get('nome_completo', 'Cliente')}</strong>,
                    </p>
                    <p style="font-size: 16px; color: #374151; line-height: 1.6;">
                        Seu pedido foi registrado com sucesso! Agora falta só uma etapa:
                    </p>
                    {info_beneficiario_email}
                    <div style="background-color: #fef3c7; border-left: 4px solid #f59e0b; padding: 15px; margin: 20px 0; border-radius: 5px;">
                        <p style="margin: 0; font-size: 16px; color: #92400e; font-weight: 600;">
                            ⚠️ IMPORTANTE: Após realizar o pagamento via PIX, você DEVE clicar no botão 
                            <strong>"Informar Pagamento"</strong> no aplicativo para que sua compra seja confirmada!
                        </p>
                    </div>
                    <h3 style="color: #1DD1A1; margin-top: 30px;">📋 Resumo do Pedido:</h3>
                    <ul style="list-style: none; padding: 0; margin: 15px 0;">
                        {lista_procedimentos}
                    </ul>
                    <div style="background-color: #f3f4f6; padding: 20px; border-radius: 8px; margin: 20px 0;">
                        <table width="100%" cellpadding="5" style="border-collapse: collapse;">
                            <tr>
                                <td style="font-size: 16px; color: #374151; padding: 5px 0;">
                                    <strong>Valor Total:</strong>
                                </td>
                                <td style="font-size: 18px; color: #1DD1A1; text-align: right; font-weight: bold; padding: 5px 0;">
                                    {formatar_moeda(total_geral)}
                                </td>
                            </tr>
                            <tr>
                                <td style="font-size: 16px; color: #10b981; padding: 5px 0;">
                                    💰 Seu cashback:
                                </td>
                                <td style="font-size: 16px; color: #10b981; text-align: right; font-weight: 600; padding: 5px 0;">
                                    {formatar_moeda(cashback_geral)}
                                </td>
                            </tr>
                        </table>
                    </div>
                    <h3 style="color: #1DD1A1; margin-top: 30px;">💳 Como Pagar:</h3>
                    <ol style="font-size: 16px; color: #374151; line-height: 1.8; padding-left: 20px;">
                        <li>Copie o código PIX Copia e Cola que apareceu na tela</li>
                        <li>Abra o aplicativo do seu banco</li>
                        <li>Escolha a opção PIX → Copia e Cola</li>
                        <li>Cole o código e confirme o pagamento</li>
                    </ol>
                    <div style="background-color: #dbeafe; border-left: 4px solid #3b82f6; padding: 15px; margin: 20px 0; border-radius: 5px;">
                        <p style="margin: 0; font-size: 16px; color: #1e3a8a; font-weight: 600;">
                            🔔 Após realizar o pagamento, não esqueça de clicar em 
                            <strong>"Informar Pagamento"</strong> no app!
                        </p>
                    </div>
                    """
                    
                    corpo_texto = f"Olá {cliente.get('nome_completo', 'Cliente')}, seu pedido foi realizado! Valor total: {formatar_moeda(total_geral)}. Após pagar via PIX, clique em 'Informar Pagamento' no app."
                    
                    email_html_completo = template_email_base("Confirmação de Pedido", conteudo_email)
                    assunto_email = f"✅ Pedido Realizado - Valor: {formatar_moeda(total_geral)}"
                    
                    enviar_email(
                        destinatario=cliente_email,
                        assunto=assunto_email,
                        corpo_html=email_html_completo,
                        corpo_texto=corpo_texto
                    )
                    print(f"✅ Email de confirmação de pedido enviado para {cliente_email}")
                else:
                    print(f"⚠️ Email não enviado (cliente sem email cadastrado)")
            except Exception as e:
                print(f"\n❌❌❌ ERRO AO ENVIAR EMAIL DE CONFIRMAÇÃO ❌❌❌")
                print(f"Mensagem: {str(e)}")
            
            # ========== 8. LIMPAR E ATUALIZAR ==========
            carrinho_cliente.set([])
            carrinho_cliente_trigger.set(carrinho_cliente_trigger() + 1)
            compras_trigger.set(compras_trigger() + 1)
            cashback_trigger.set(cashback_trigger() + 1)
            minhas_compras_trigger.set(minhas_compras_trigger() + 1)

            print(f"{len(vendas_criadas)} venda(s) criada(s)!")
            print("="*60 + "\n")

            # Notificação final
            mensagem_tipo = ""
            if dados_benef['tipo_compra'] == 'presente':
                mensagem_tipo = f"<p style='margin: 0.5rem 0; color: #f59e0b; font-size: 0.95rem;'>🎁 Presente para: {dados_benef['beneficiario_nome']}</p>"
            elif dados_benef['tipo_compra'] == 'terceiro':
                mensagem_tipo = f"<p style='margin: 0.5rem 0; color: #3b82f6; font-size: 0.95rem;'>👥 Exame para: {dados_benef['beneficiario_nome']}</p>"

            ui.notification_show(
                ui.HTML(f"""
                <div style="text-align: center;">
                    <div style="font-size: 2rem; margin-bottom: 0.5rem;">✅</div>
                    <h5 style="margin: 0 0 0.5rem 0; color: #2D3748;">Pedido Realizado!</h5>
                    {mensagem_tipo}
                    <p style="margin: 0 0 0.5rem 0; font-size: 1.1rem; color: #1DD1A1; font-weight: 600;">
                        💰 Valor: {formatar_moeda(total_geral)}
                    </p>
                    <p style="margin: 0 0 0.5rem 0; color: #546E7A; font-size: 0.95rem;">
                        Pague com o PIX Copia e Cola exibido na tela.
                    </p>
                    <div style="background: #dbeafe; padding: 0.75rem; border-radius: 0.5rem; margin-top: 0.75rem;">
                        <p style="margin: 0; color: #1e40af; font-size: 0.9rem;">
                            📧 Um email foi enviado para {cliente.get('email', 'seu email')} com os detalhes.
                        </p>
                    </div>
                </div>
                """),
                type="message",
                duration=15
            )

        except Exception as e:
            print(f"❌ Erro em finalizar_compra_cliente: {e}")
            import traceback
            traceback.print_exc()
            ui.notification_show(f"❌ Erro ao finalizar compra: {str(e)}", type="error")
        
    @reactive.Effect
    @reactive.event(input.btn_buscar_proc_cliente)
    def buscar_procedimentos_cliente():
        """Busca procedimentos"""
        try:
            print("\n🔴 BOTÃO BUSCAR CLICADO!")
            
            termo_busca = input.buscar_procedimento_cliente()
            
            if not termo_busca or len(termo_busca) < 3:
                ui.notification_show("⚠️ Digite pelo menos 3 caracteres!", type="warning")
                return
            
            if not supabase:
                ui.notification_show("❌ Erro de conexão", type="error")
                return
            
            user = user_data()
            if not user:
                ui.notification_show("❌ Faça login", type="error")
                return
            
            # Busca dados do cliente
            cliente_result = supabase.table('clientes').select('*').eq('usuario_id', user['id']).execute()
            
            if not cliente_result.data:
                ui.notification_show("⚠️ Complete seu cadastro", type="warning")
                return
            
            cliente = cliente_result.data[0]
            
            # Tenta GPS
            cliente_lat = cliente.get('latitude')
            cliente_lon = cliente.get('longitude')
            usa_gps = cliente.get('usa_geolocalizacao', False)
            
            # Tenta cidade selecionada
            cidade_selecionada = None
            estado_selecionado = None
            
            try:
                dados_cidade = input.cidade_selecionada_busca()
                if dados_cidade:
                    cidade_selecionada = dados_cidade.get('cidade')
                    estado_selecionado = dados_cidade.get('estado')
            except:
                pass
            
            # Define cidade e estado
            if cidade_selecionada and estado_selecionado:
                cidade = cidade_selecionada
                estado = estado_selecionado
                cliente_lat = None
                cliente_lon = None
            elif usa_gps and cliente_lat and cliente_lon:
                cidade = cliente.get('endereco_cidade')
                estado = cliente.get('endereco_estado')
            else:
                cidade = cliente.get('endereco_cidade')
                estado = cliente.get('endereco_estado')
            
            print(f"🔍 Buscando: {termo_busca}")
            print(f"GPS: {cliente_lat}, {cliente_lon}" if cliente_lat else f"Cidade: {cidade}/{estado}")
            
            # Busca híbrida
            procedimentos = buscar_procedimentos_hibrido(
                termo_busca=termo_busca,
                cliente_lat=cliente_lat,
                cliente_lon=cliente_lon,
                cidade=cidade,
                estado=estado,
                raio_km=50
            )
            
            if not procedimentos:
                busca_procedimentos.set([])
                ui.notification_show(f"😔 Nenhum resultado para '{termo_busca}'", type="warning")
                return
            
            busca_procedimentos.set(procedimentos)
            
            modo = procedimentos[0].get('modo_busca', 'geral')
            
            if modo == 'gps':
                distancia = procedimentos[0].get('distancia_km', 0)
                mensagem = f"✅ {len(procedimentos)} resultados!\n📍 Mais próximo: {distancia} km"
            elif modo == 'cidade':
                mensagem = f"✅ {len(procedimentos)} resultados em {cidade}!"
            else:
                mensagem = f"✅ {len(procedimentos)} resultados!"
            
            ui.notification_show(mensagem, type="message", duration=5)
            print(f"✅ {len(procedimentos)} procedimentos encontrados!\n")
            
        except Exception as e:
            print(f"❌ ERRO: {e}")
            import traceback
            traceback.print_exc()
            ui.notification_show(f"❌ Erro: {str(e)}", type="error")

# ========== 5. LISTA DE COMPRAS DO CLIENTE  ==========
    @output
    @render.ui
    def lista_minhas_compras_cliente():
        minhas_compras_trigger() # Depende do trigger
        try:
            user = user_data()
            if not user or not supabase:
                return ui.div()

            # Busca cliente completo
            cliente_result = supabase.table('clientes').select('*').eq('usuario_id', user['id']).execute()
            if not cliente_result.data:
                return ui.div( {"style": "text-align: center; padding: 3rem; color: #94a3b8;"}, ui.h5("Nenhuma compra realizada"))
            
            cliente_data = cliente_result.data[0] # Dados do comprador
            cliente_id = cliente_data['id']

            # Busca vendas (incluindo a nova URL da imagem)
            result = supabase.table('vendas').select(
                '*, clinicas(*), itens_venda(*)'
            ).eq('cliente_id', cliente_id).order('criado_em', desc=True).execute()

            if not result.data:
                 return ui.div( {"style": "text-align: center; padding: 3rem; color: #94a3b8;"}, ui.h5("Nenhuma compra realizada"), ui.p("Suas compras aparecerão aqui"))

            cards = []
            for venda in result.data:
                status_venda = venda.get('status')
                pagamento_confirmado = venda.get('pagamento_confirmado', False)
                pagamento_informado = venda.get('pagamento_informado', False)
                comprovante_url = venda.get('comprovante_url')
                venda_id_str = str(venda['id'])
                numero_venda = venda.get('numero_venda', 'N/A')
                expira_em = venda.get('expira_em')

                # Status
                if pagamento_confirmado:
                    status = "Confirmado - Agende!"
                    cor_status = "#10b981"
                elif pagamento_informado:
                    status = "Aguardando Confirmação"
                    cor_status = "#f59e0b"
                elif status_venda == 'aguardando_pagamento':
                    status = "Aguardando Pagamento"
                    cor_status = "#ef4444"
                else:
                    status = status_venda.replace('_', ' ').title() if status_venda else "Status Desconhecido"
                    cor_status = "#546E7A"

                clinica = venda.get('clinicas', {})
                clinica_nome = clinica.get('nome_fantasia') or clinica.get('razao_social', 'N/A')
                itens = venda.get('itens_venda', [])
                data_compra = pd.to_datetime(venda['criado_em']).strftime('%d/%m/%Y %H:%M')

                # ========== TIMER DE EXPIRAÇÃO (1 HORA) ==========
                timer_html = ""
                if status_venda == 'aguardando_pagamento' and not pagamento_informado and expira_em:
                    timer_id = f"timer_{venda_id_str}"
                    timer_html = f'''
                    <div id="{timer_id}" style="
                        background: linear-gradient(135deg, #fee2e2, #fecaca);
                        border: 2px solid #ef4444;
                        border-radius: 0.75rem;
                        padding: 1rem;
                        margin: 1rem 0;
                        text-align: center;
                    ">
                        <div style="font-size: 1.1rem; font-weight: 700; color: #991b1b; margin-bottom: 0.5rem;">
                            ⏰ ATENÇÃO: Tempo Limite para Pagamento
                        </div>
                        <div style="font-size: 2rem; font-weight: 700; color: #dc2626; margin: 0.5rem 0;" id="{timer_id}_display">
                            --:--:--
                        </div>
                        <div style="font-size: 0.9rem; color: #7f1d1d; line-height: 1.5;">
                            Você tem <strong>1 HORA</strong> para realizar o pagamento e clicar em <strong>"Informar Pagamento"</strong>.<br>
                            <span style="font-size: 0.85rem;">Caso contrário, este pedido será <strong>cancelado automaticamente</strong> e você terá que refazer.</span>
                        </div>
                    </div>
                    <script>
                    (function() {{
                        const expiraEm = new Date('{expira_em}');
                        const timerId = '{timer_id}';
                        const displayId = '{timer_id}_display';
                        const vendaId = '{venda_id_str}';
                        
                        function atualizarTimer() {{
                            const agora = new Date();
                            const diff = expiraEm - agora;
                            
                            if (diff <= 0) {{
                                document.getElementById(displayId).innerHTML = '⏰ EXPIRADO';
                                document.getElementById(timerId).style.background = 'linear-gradient(135deg, #7f1d1d, #991b1b)';
                                document.getElementById(displayId).style.color = 'white';
                                
                                // Notifica o servidor para deletar a venda
                                Shiny.setInputValue('venda_expirada', vendaId, {{priority: 'event'}});
                                return;
                            }}
                            
                            const horas = Math.floor(diff / (1000 * 60 * 60));
                            const minutos = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
                            const segundos = Math.floor((diff % (1000 * 60)) / 1000);
                            
                            const horasStr = String(horas).padStart(2, '0');
                            const minutosStr = String(minutos).padStart(2, '0');
                            const segundosStr = String(segundos).padStart(2, '0');
                            
                            document.getElementById(displayId).innerHTML = horasStr + ':' + minutosStr + ':' + segundosStr;
                            
                            // Muda cor se faltam menos de 10 minutos
                            if (diff < 10 * 60 * 1000) {{
                                document.getElementById(timerId).style.background = 'linear-gradient(135deg, #7f1d1d, #991b1b)';
                                document.getElementById(displayId).style.color = 'white';
                            }}
                            
                            setTimeout(atualizarTimer, 1000);
                        }}
                        
                        atualizarTimer();
                    }})();
                    </script>
                    '''

                # ========== CÓDIGO VND CLICÁVEL (se pagamento confirmado) ==========
                if pagamento_confirmado:
                    # Busca cashback
                    cashback_result = supabase.table('cashback_pagamentos').select('valor, pago').eq('venda_id', venda['id']).execute()
                    cashback_valor = 0
                    cashback_pago = False
                    if cashback_result.data:
                        cashback_valor = sum([float(c.get('valor', 0) or 0) for c in cashback_result.data])
                        cashback_pago = all([c.get('pago', False) for c in cashback_result.data])
                    
                    # Formata contatos
                    whatsapp = clinica.get('whatsapp', '')
                    telefone = clinica.get('telefone', '')
                    email = clinica.get('email', '')
                    endereco = clinica.get('endereco_rua', '')
                    cidade = clinica.get('endereco_cidade', '')
                    estado = clinica.get('endereco_estado', '')
                    
                    whatsapp_formatado = formatar_whatsapp(whatsapp) if whatsapp else 'Não informado'
                    telefone_formatado = formatar_whatsapp(telefone) if telefone else 'Não informado'
                    endereco_completo = f"{endereco}, {cidade}/{estado}" if endereco else f"{cidade}/{estado}" if cidade else "Não informado"
                    
                    # Calcula dias restantes (30 dias a partir da confirmação)
                    try:
                        data_confirmacao = pd.to_datetime(venda.get('data_pagamento_confirmado'))
                        dias_passados = (pd.Timestamp.now() - data_confirmacao).days
                        dias_restantes = max(0, 30 - dias_passados)
                    except:
                        dias_restantes = 30
                    
                    numero_venda_html = f'''
                    <h6 style="margin: 0 0 0.5rem 0;">
                        <span style="
                            cursor: pointer;
                            color: #1DD1A1;
                            font-weight: 700;
                            text-decoration: underline;
                            transition: all 0.2s;
                        " 
                        onmouseover="this.style.color='#4f46e5'; this.style.transform='scale(1.05)';"
                        onmouseout="this.style.color='#1DD1A1'; this.style.transform='scale(1)';"
                        onclick="
                            Shiny.setInputValue('abrir_info_clinica', JSON.stringify({{
                                venda_id: '{venda_id_str}',
                                numero_venda: '{numero_venda}',
                                clinica_nome: '{clinica_nome}',
                                whatsapp: '{whatsapp}',
                                whatsapp_formatado: '{whatsapp_formatado}',
                                telefone_formatado: '{telefone_formatado}',
                                email: '{email}',
                                endereco_completo: '{endereco_completo}',
                                cashback_valor: {cashback_valor},
                                cashback_pago: {str(cashback_pago).lower()},
                                dias_restantes: {dias_restantes}
                            }}), {{priority: 'event'}});
                        ">
                            📋 {numero_venda}
                        </span>
                        <span style="font-size: 0.75rem; color: #546E7A; font-weight: normal; margin-left: 0.5rem;">
                            (clique para ver detalhes)
                        </span>
                    </h6>
                    '''
                else:
                    numero_venda_html = f'<h6 style="margin: 0 0 0.5rem 0;">📋 {numero_venda}</h6>'
                # ==========================================================================

                # ==================================
                # === INÍCIO: LÓGICA DOS BOTÕES (RESTAURADA) ===
                # ==================================
                botoes_ui = []
                if status_venda == 'aguardando_pagamento':
                    botoes_ui.append(
                        ui.tags.button(
                            "💳 Pagar com PIX",
                            class_="btn btn-info w-100 mb-2",
                            onclick=f"Shiny.setInputValue('pagar_compra_id', '{venda_id_str}', {{priority: 'event'}})",
                            style="font-weight: 600; font-size: 0.85rem;"
                        )
                    )
                    mensagem_alerta_js = (
                        "IMPORTANTE:\\n\\n"
                        "1. Clique em OK somente APÓS realizar o pagamento PIX.\\n"
                        "2. Após clicar OK, você precisará ENVIAR O COMPROVANTE para validar seu cashback.\\n\\n"
                        "Confirmar que o pagamento foi realizado?"
                    )
                    botoes_ui.append(
                        ui.tags.button(
                            "✅ Informar Pagamento Realizado",
                            class_="btn btn-success w-100",
                            onclick=(
                                f"if (confirm('{mensagem_alerta_js}')) {{ "
                                f"Shiny.setInputValue('informar_pagamento_id', '{venda_id_str}', {{priority: 'event'}}); "
                                f"}} else {{ console.log('Informar pagamento cancelado.'); }}"
                            ),
                            style="font-weight: 600; font-size: 0.85rem;"
                        )
                    )
                elif pagamento_informado and not pagamento_confirmado:
                    if comprovante_url:
                        botoes_ui.append(
                            ui.div(
                                {"class": "btn btn-light w-100 disabled", "style": "font-weight: 600; font-size: 0.85rem; border-color: #10b981; color: #10b981;"},
                                "✅ Comprovante Enviado"
                            )
                        )
                        botoes_ui.append(
                             ui.div(
                                 {"style": "font-size: 0.75rem; color: #546E7A; text-align: center; margin-top: 0.5rem;"},
                                "Aguardando Confirmação..."
                             )
                        )
                    else:
                        botoes_ui.append(
                            ui.tags.button(
                                "✉️ Enviar Comprovante (Obrigatório p/ Cashback)",
                                class_="btn btn-warning w-100",
                                onclick=f"Shiny.setInputValue('trigger_comprovante_modal', '{venda_id_str}', {{priority: 'event'}})",
                                style="font-weight: 600; font-size: 0.85rem;"
                            )
                        )
                elif pagamento_confirmado:
                     botoes_ui.append(
                         ui.div(
                             {"class": "btn btn-success w-100 disabled", "style": "font-weight: 600; font-size: 0.85rem;"},
                             "✅ Pagamento Confirmado"
                         )
                     )
                     if comprovante_url:
                         botoes_ui.append(
                             ui.div(
                                  {"style": "font-size: 0.75rem; color: #10b981; text-align: center; margin-top: 0.5rem;"},
                                 "Comprovante Enviado"
                              )
                         )
                # ==================================
                # === FIM: LÓGICA DOS BOTÕES ===
                # ==================================

                
                # =================================================================
                # === INÍCIO: BLOCO WHATSAPP BENEFICIÁRIO (AGORA USANDO A URL) ===
                # =================================================================
                tipo_compra = venda.get('tipo_compra', 'proprio')
                bloco_whatsapp_ui = None
                
                # Pega a URL da imagem que o admin gerou
                url_imagem_gerada = venda.get('url_imagem_beneficiario')

                if tipo_compra != 'proprio':
                    if pagamento_confirmado and url_imagem_gerada:
                        # PAGAMENTO CONFIRMADO E IMAGEM PRONTA
                        
                        nome_arquivo_imagem = f"MedPIX_{numero_venda}.png"
                        
                        # Monta a mensagem de texto para o WhatsApp
                        msg_base = f"Olá, {venda.get('beneficiario_nome', '').split()[0]}!"
                        
                        if tipo_compra == 'presente':
                            msg_whatsapp = (
                                f"{msg_base} 🎁\n\n"
                                f"{cliente_data.get('nome_completo', 'Alguém')} te deu um presente para cuidar da saúde!\n\n"
                                f"Este é seu código de atendimento: *{numero_venda}*.\n"
                                f"Você tem 30 dias para agendar na *{clinica_nome}*!"
                            )
                        else: # "para_outra_pessoa"
                            msg_whatsapp = (
                                f"{msg_base}\n\n"
                                f"Seguem os detalhes para seu atendimento na *{clinica_nome}*.\n"
                                f"Seu código é *{numero_venda}*.\n\n"
                                f"A imagem em anexo tem os detalhes do PIX para pagamento.\n"
                                f"⚠️ Lembre-se do prazo de 30 dias para agendar!"
                            )
                        
                        # URL de fallback (somente texto)
                        url_whatsapp_fallback = f"https://wa.me/?text={urllib.parse.quote(msg_whatsapp)}"

                        # Converte os argumentos para strings JS seguras
                        js_download_url = json.dumps(url_imagem_gerada) # <-- USA A URL PÚBLICA
                        js_text_message = json.dumps(msg_whatsapp)
                        js_filename = json.dumps(nome_arquivo_imagem)
                        js_fallback_url = json.dumps(url_whatsapp_fallback)
                        
                        bloco_whatsapp_ui = ui.div(
                            {"style": "background: linear-gradient(135deg, #dcfce7, #bbf7d0); border-radius: 0.75rem; padding: 1.25rem; margin-top: 1rem; border: 2px solid #10b981;"},
                            ui.h5("🎁 Enviar para o Beneficiário", style="color: #15803d; margin: 0 0 1rem 0; text-align: center;"),
                            ui.p("O pagamento foi confirmado! Clique abaixo para compartilhar a imagem com o beneficiário.", style="font-size: 0.9rem; text-align: center; color: #166534;"),
                            
                            # Botão único que chama o JavaScript
                            ui.tags.button(
                                "📱 Compartilhar no WhatsApp",
                                class_="btn btn-success w-100",
                                style="font-weight: 600;",
                                onclick=f"shareOnWhatsApp({js_download_url}, {js_text_message}, {js_filename}, {js_fallback_url})"
                            )
                        )
                        
                    elif pagamento_confirmado and not url_imagem_gerada:
                        # PAGAMENTO CONFIRMADO, MAS IMAGEM AINDA NÃO FOI PROCESSADA
                        bloco_whatsapp_ui = ui.div(
                            {"style": "background: #dbeafe; border-radius: 0.75rem; padding: 1.25rem; margin-top: 1rem; border: 2px solid #3b82f6;"},
                            ui.h5("🎁 Envio para Beneficiário", style="color: #1e40af; margin: 0 0 0.5rem 0; text-align: center;"),
                            ui.p("🔄 Estamos processando a imagem para compartilhamento. Atualize em alguns instantes.", style="font-size: 0.9rem; text-align: center; color: #1e3a8a;")
                        )
                        
                    elif not pagamento_confirmado:
                        # PAGAMENTO AINDA PENDENTE
                        bloco_whatsapp_ui = ui.div(
                            {"style": "background: #fef3c7; border-radius: 0.75rem; padding: 1.25rem; margin-top: 1rem; border: 2px solid #f59e0b;"},
                            ui.h5("🎁 Envio para Beneficiário", style="color: #92400e; margin: 0 0 0.5rem 0; text-align: center;"),
                            ui.p("⏳ Assim que o pagamento for confirmado, o botão para compartilhar os detalhes com o beneficiário aparecerá aqui.", style="font-size: 0.9rem; text-align: center; color: #78350f;")
                        )
                
                # ================================================
                # === FIM: BLOCO WHATSAPP BENEFICIÁRIO ===
                # ================================================
                
                card = ui.div(
                    {"class": "card-custom", "style": f"margin-bottom: 1rem; border-left: 4px solid {cor_status};"},
                    ui.HTML(timer_html),  # Timer (existente)
                    ui.row(
                        ui.column(8,
                            ui.HTML(numero_venda_html),
                            ui.p(f"🏥 {clinica_nome}", style="margin: 0.25rem 0; font-size: 0.9rem;"),
                            ui.p(f"📅 {data_compra}", style="margin: 0.25rem 0; font-size: 0.85rem; color: #546E7A;"),
                            ui.p(f"📦 {len(itens)} procedimento(s)", style="margin: 0.25rem 0; font-size: 0.9rem;"),
                            ui.p(f"💰 {formatar_moeda(venda['valor_total'])}",
                                 style="margin: 0.25rem 0; font-weight: 700; color: #1DD1A1; font-size: 1rem;")
                        ),
                        ui.column(4,
                            ui.div(
                                {"style": "text-align: right;"},
                                ui.p(status, style=f"margin: 0 0 1rem 0; font-weight: 600; color: {cor_status}; font-size: 0.9rem;"),
                                *botoes_ui # <-- AQUI OS BOTÕES SÃO RENDERIZADOS
                            )
                        )
                    ),
                    
                    bloco_whatsapp_ui if bloco_whatsapp_ui else ui.div() # <-- ADICIONA O NOVO BLOCO AQUI
                )
                cards.append(card)

            return ui.div(*cards)

        except Exception as e:
            print(f"Erro lista_minhas_compras_cliente: {e}")
            import traceback
            traceback.print_exc()
            return ui.div(ui.p(f"Erro ao carregar compras: {str(e)}", style="color: red;"))

    @reactive.Effect
    def _monitor_abrir_info_clinica():
        """Abre modal com informações da clínica e orientações"""
        try:
            dados_json = None
            try:
                dados_json = input.abrir_info_clinica()
            except:
                return
            
            if not dados_json:
                return
            
            import json
            dados = json.loads(dados_json)
            
            numero_venda = dados.get('numero_venda')
            clinica_nome = dados.get('clinica_nome')
            whatsapp = dados.get('whatsapp')
            whatsapp_formatado = dados.get('whatsapp_formatado')
            telefone_formatado = dados.get('telefone_formatado')
            email = dados.get('email')
            endereco_completo = dados.get('endereco_completo')
            cashback_valor = dados.get('cashback_valor', 0)
            cashback_pago = dados.get('cashback_pago', False)
            dias_restantes = dados.get('dias_restantes', 30)
            
            # Define cor do alerta de prazo
            if dias_restantes > 15:
                cor_prazo = "#10b981"
                icone_prazo = "✅"
            elif dias_restantes > 7:
                cor_prazo = "#f59e0b"
                icone_prazo = "⚠️"
            else:
                cor_prazo = "#ef4444"
                icone_prazo = "🚨"
            
            # Monta link do WhatsApp
            whatsapp_link = ""
            if whatsapp:
                whatsapp_limpo = ''.join(filter(str.isdigit, whatsapp))
                whatsapp_link = f"https://wa.me/{whatsapp_limpo}"
            
            modal_info_html = f'''
            <div id="modal_info_clinica" style="
                position: fixed; top: 0; left: 0; width: 100%; height: 100%;
                background: rgba(0,0,0,0.9); z-index: 10003;
                display: flex; align-items: center; justify-content: center;
                overflow-y: auto; padding: 1rem;
                animation: fadeIn 0.3s ease-in;
            ">
                <div style="
                    background: linear-gradient(135deg, #1DD1A1 0%, #0D9488 100%);
                    border-radius: 1.5rem; padding: 2rem;
                    max-width: 95%; width: 550px;
                    max-height: 90vh; overflow-y: auto;
                    box-shadow: 0 20px 60px rgba(0,0,0,0.5);
                    animation: slideUp 0.4s ease-out;
                    color: white;
                " onclick="event.stopPropagation()">
                    
                    <!-- Cabeçalho -->
                    <div style="text-align: center; margin-bottom: 1.5rem;">
                        <div style="font-size: 3rem; margin-bottom: 0.5rem;">🏥</div>
                        <h2 style="margin: 0 0 0.5rem 0; font-size: 1.5rem; font-weight: 800;">
                            Informações do Atendimento
                        </h2>
                        <p style="margin: 0; opacity: 0.9; font-size: 0.9rem;">
                            Venda: {numero_venda}
                        </p>
                    </div>
                    
                    <!-- Dados da Clínica -->
                    <div style="
                        background: rgba(255,255,255,0.15);
                        backdrop-filter: blur(10px);
                        border-radius: 1rem;
                        padding: 1.5rem;
                        margin-bottom: 1.5rem;
                        border: 2px solid rgba(255,255,255,0.2);
                    ">
                        <h3 style="margin: 0 0 1rem 0; font-size: 1.1rem; text-align: center;">
                            🏥 {clinica_nome}
                        </h3>
                        
                        <div style="margin-bottom: 0.75rem;">
                            <div style="display: flex; align-items: center; gap: 0.75rem;">
                                <span style="font-size: 1.5rem;">📱</span>
                                <div style="flex: 1;">
                                    <strong style="font-size: 0.85rem; opacity: 0.9;">WhatsApp:</strong>
                                    <p style="margin: 0.25rem 0 0 0; font-size: 0.95rem;">
                                        {whatsapp_formatado}
                                    </p>
                                </div>
                            </div>
                        </div>
                        
                        {'<div style="margin-bottom: 0.75rem;"><div style="display: flex; align-items: center; gap: 0.75rem;"><span style="font-size: 1.5rem;">☎️</span><div style="flex: 1;"><strong style="font-size: 0.85rem; opacity: 0.9;">Telefone:</strong><p style="margin: 0.25rem 0 0 0; font-size: 0.95rem;">' + telefone_formatado + '</p></div></div></div>' if telefone_formatado != 'Não informado' else ''}
                        
                        {'<div style="margin-bottom: 0.75rem;"><div style="display: flex; align-items: center; gap: 0.75rem;"><span style="font-size: 1.5rem;">📧</span><div style="flex: 1;"><strong style="font-size: 0.85rem; opacity: 0.9;">Email:</strong><p style="margin: 0.25rem 0 0 0; font-size: 0.85rem; word-break: break-word;">' + email + '</p></div></div></div>' if email else ''}
                        
                        <div>
                            <div style="display: flex; align-items: start; gap: 0.75rem;">
                                <span style="font-size: 1.5rem;">📍</span>
                                <div style="flex: 1;">
                                    <strong style="font-size: 0.85rem; opacity: 0.9;">Endereço:</strong>
                                    <p style="margin: 0.25rem 0 0 0; font-size: 0.85rem; line-height: 1.4;">
                                        {endereco_completo}
                                    </p>
                                </div>
                            </div>
                        </div>
                        
                        {f'<a href="{whatsapp_link}" target="_blank" style="display: block; text-align: center; background: #25D366; color: white; padding: 0.75rem; border-radius: 0.5rem; text-decoration: none; font-weight: 600; margin-top: 1rem; transition: all 0.3s;" onmouseover="this.style.transform=\'scale(1.02)\'" onmouseout="this.style.transform=\'scale(1)\'">💬 Abrir WhatsApp</a>' if whatsapp_link else ''}
                    </div>
                    
                    <!-- Alerta de Prazo -->
                    <div style="
                        background: {cor_prazo};
                        border-radius: 1rem;
                        padding: 1.25rem;
                        margin-bottom: 1.5rem;
                        text-align: center;
                        box-shadow: 0 4px 12px rgba(0,0,0,0.2);
                    ">
                        <div style="font-size: 2.5rem; margin-bottom: 0.5rem;">{icone_prazo}</div>
                        <h3 style="margin: 0 0 0.5rem 0; font-size: 1.2rem; font-weight: 700;">
                            {dias_restantes} dias restantes
                        </h3>
                        <p style="margin: 0; font-size: 0.9rem; opacity: 0.95;">
                            para agendar seu atendimento
                        </p>
                    </div>
                    
                    <!-- Info Cashback -->
                    <div style="
                        background: rgba(255,255,255,0.15);
                        border-radius: 1rem;
                        padding: 1.25rem;
                        margin-bottom: 1.5rem;
                        text-align: center;
                        border: 2px solid rgba(255,255,255,0.2);
                    ">
                        <div style="font-size: 2rem; margin-bottom: 0.5rem;">💰</div>
                        <h3 style="margin: 0 0 0.5rem 0; font-size: 1.1rem;">Cashback</h3>
                        <p style="margin: 0 0 0.5rem 0; font-size: 1.3rem; font-weight: 700;">
                            {formatar_moeda(cashback_valor)}
                        </p>
                        <p style="margin: 0; font-size: 0.85rem; opacity: 0.9;">
                            {('✅ Já recebido!' if cashback_pago else '⏳ Será pago em até 2 dias úteis')}
                        </p>
                    </div>
                    
                    <!-- Botão -->
                    <button onclick="document.getElementById('modal_info_clinica').remove()" style="
                        background: white;
                        color: #1DD1A1;
                        border: none;
                        padding: 1rem;
                        border-radius: 0.75rem;
                        font-weight: 700;
                        font-size: 1rem;
                        cursor: pointer;
                        width: 100%;
                        box-shadow: 0 4px 12px rgba(0,0,0,0.2);
                        transition: all 0.3s;
                    " onmouseover="this.style.transform='scale(1.02)'" onmouseout="this.style.transform='scale(1)'">
                        Fechar
                    </button>
                </div>
            </div>
            
            <style>
                @keyframes fadeIn {{
                    from {{ opacity: 0; }}
                    to {{ opacity: 1; }}
                }}
                @keyframes slideUp {{
                    from {{ transform: translateY(50px); opacity: 0; }}
                    to {{ transform: translateY(0); opacity: 1; }}
                }}
            </style>
            '''
            
            ui.insert_ui(
                selector="body",
                where="beforeEnd",
                ui=ui.HTML(modal_info_html)
            )
            
        except Exception as e:
            print(f"❌ Erro _monitor_abrir_info_clinica: {e}")
            import traceback
            traceback.print_exc()

# ========== 8. RE-EXIBIR MODAL PIX PARA PAGAMENTO PENDENTE ==========
    @reactive.Effect
    def _monitor_pagar_compra_id():
        """Exibe o modal de pagamento PIX para uma compra pendente"""
        global PIX_COPIA_E_COLA_EMPRESA # Acessa a constante global
        try:
            venda_id = None
            try:
                venda_id = input.pagar_compra_id()
            except:
                return # Sai se o input não existir

            if not venda_id or not supabase:
                return # Sai se não houver ID ou conexão

            print(f"\n💳 RE-EXIBINDO PIX PARA PAGAMENTO - DEBUG")
            print(f"Venda ID: {venda_id}")

            # Busca os dados da venda específica
            venda_result = supabase.table('vendas').select(
                '*, clinicas(razao_social, nome_fantasia), itens_venda(*)'
            ).eq('id', venda_id).execute()

            if not venda_result.data:
                ui.notification_show("❌ Venda não encontrada!", type="error")
                return

            venda = venda_result.data[0]
            clinica = venda.get('clinicas', {})
            clinica_nome = clinica.get('nome_fantasia') or clinica.get('razao_social', 'N/A')
            valor_total = venda.get('valor_total', 0)
            numero_venda = venda.get('numero_venda', 'N/A')

            # Busca cashback (se houver)
            cashback_total = 0
            cashback_result = supabase.table('cashback_pagamentos').select('valor').eq('venda_id', venda_id).execute()
            if cashback_result.data:
                cashback_total = sum([float(c.get('valor', 0) or 0) for c in cashback_result.data])

            print(f"Valor: {formatar_moeda(valor_total)}, Cashback: {formatar_moeda(cashback_total)}")

            # ID único para o elemento que contém o código PIX
            pix_code_id = f"pixCode_{venda_id}" # Usa o ID da venda

            modal_html = f'''
            <div id="pix_payment_modal_{venda_id}" style="
                position: fixed; top: 0; left: 0; width: 100%; height: 100%;
                background: rgba(0,0,0,0.8); z-index: 10000;
                display: flex; align-items: center; justify-content: center;
                overflow-y: auto; padding: 1rem;
            ">
                <div style="
                    background: white; border-radius: 1rem; padding: 2rem;
                    max-width: 95%; width: 550px;
                    text-align: center; box-shadow: 0 5px 15px rgba(0,0,0,0.3);
                " onclick="event.stopPropagation()"> <h3 style="color: #10b981; margin-bottom: 1rem;"> Pagar com PIX</h3>
                    <p style="color: #546E7A; margin-bottom: 1.5rem;">
                        Copie o código abaixo e cole no seu aplicativo do banco para pagar.
                    </p>

                    <div style="margin-bottom: 1rem;">
                        <h5 style="margin: 0 0 0.5rem 0;">Resumo da Compra:</h5>
                        <p style='margin: 0.25rem 0; font-size: 0.9rem;'><b>{clinica_nome}</b>: {numero_venda}</p>
                        <hr style="margin: 0.5rem 0;">
                        <p style="margin: 0.5rem 0; font-size: 1.1rem;"><b>Valor Total: {formatar_moeda(valor_total)}</b></p>
                        <p style="margin: 0.25rem 0; font-size: 0.9rem; color: #10b981;">Cashback a receber: {formatar_moeda(cashback_total)}</p>
                    </div>

                    <div style="
                        background: #f1f5f9; padding: 1rem; border-radius: 0.5rem;
                        margin: 1.5rem 0; word-break: break-all; font-family: monospace;
                        font-size: 0.8rem; text-align: left; max-height: 100px; overflow-y: auto;
                    " id="{pix_code_id}">
                        {PIX_COPIA_E_COLA_EMPRESA}
                    </div>

                    <button id="copyPixBtn_{venda_id}" onclick="
                        const textToCopy = document.getElementById('{pix_code_id}').innerText;
                        navigator.clipboard.writeText(textToCopy).then(() => {{
                            let btn = document.getElementById('copyPixBtn_{venda_id}');
                            btn.innerText = '✅ Copiado!';
                            btn.style.background = '#059669';
                            setTimeout(() => {{
                                btn.innerText = 'Copiar Código PIX';
                                btn.style.background = '#10b981';
                            }}, 2500);
                        }}).catch(err => {{
                            console.error('Erro ao copiar:', err);
                            alert('Erro ao copiar o código. Tente selecionar e copiar manualmente.');
                        }});
                    " style="
                        background: #10b981; color: white; border: none;
                        padding: 0.75rem 1.5rem; border-radius: 0.5rem;
                        font-weight: 600; cursor: pointer; width: 100%; margin-bottom: 1rem;
                        transition: background 0.3s; font-size: 1rem;
                    ">Copiar Código PIX</button>

                    <button onclick="document.getElementById('pix_payment_modal_{venda_id}').remove()"
                        style="
                            background: #546E7A; color: white; border: none;
                            padding: 0.6rem 1.5rem; border-radius: 0.5rem;
                            font-weight: 500; cursor: pointer; width: 100%;
                            transition: background 0.3s; font-size: 0.9rem;
                        ">Fechar</button>

                     <p style="font-size: 0.8rem; color: #546E7A; margin-top: 1rem;">
                        Após o pagamento, aguarde a confirmação no app.
                     </p>
                </div>
            </div>
            '''

            # Insere o modal na página
            ui.insert_ui(
                selector="body",
                where="beforeEnd",
                ui=ui.HTML(modal_html)
            )
            print(f"✅ Modal PIX re-exibido para Venda ID: {venda_id}")

        except Exception as e:
            print(f"❌ Erro em _monitor_pagar_compra_id: {e}")
            import traceback
            traceback.print_exc()
            ui.notification_show(f"❌ Erro ao exibir pagamento: {str(e)}", type="error")


# ========== 11. CONTROLES DO MODAL DE COMPROVANTE E UPLOAD ==========

    @reactive.Effect
    @reactive.event(input.trigger_comprovante_modal)
    def _abrir_modal_comprovante():
        """Define o ID da venda para qual o modal de comprovante deve ser aberto."""
        venda_id = input.trigger_comprovante_modal()
        print(f"Modal de comprovante solicitado para Venda ID: {venda_id}")
        venda_id_para_comprovante.set(venda_id)
        # A linha ui.update_file_input foi removida


    @reactive.Effect
    @reactive.event(input.cancelar_envio_comprovante)
    def _fechar_modal_comprovante():
        """Limpa o ID da venda, fechando o modal."""
        print("Fechando modal de comprovante.")
        venda_id_para_comprovante.set(None)


    @reactive.Effect
    @reactive.event(input.btn_confirmar_envio_comprovante)
    def _processar_envio_comprovante():
        """Processa o upload do arquivo de comprovante para o Supabase Storage."""
        venda_id = venda_id_para_comprovante()
        file_info_list = input.upload_comprovante_input()

        if not venda_id or not file_info_list or not supabase:
            if not file_info_list:
                ui.notification_show("⚠️ Selecione um arquivo de comprovante primeiro!", type="warning")
            return

        try:
            print(f"\n✉️ ENVIANDO COMPROVANTE - DEBUG")
            print(f"Venda ID: {venda_id}")

            file_info = file_info_list[0]
            file_path = file_info['datapath']
            original_filename = file_info['name']
            file_type = file_info['type']

            print(f"Arquivo: {original_filename} ({file_type})")
            print(f"Path temporário: {file_path}")

            # Lê os bytes do arquivo
            with open(file_path, 'rb') as f:
                file_bytes = f.read()
            print(f"Tamanho: {len(file_bytes)} bytes")

            # Busca CPF do cliente para nomear o arquivo
            cliente_cpf = "CPF_NAO_ENCONTRADO"
            try:
                venda_res = supabase.table('vendas').select('clientes(cpf)').eq('id', venda_id).single().execute()
                if venda_res.data and venda_res.data.get('clientes'):
                    cliente_cpf = venda_res.data['clientes'].get('cpf', cliente_cpf)
            except Exception as e:
                print(f"Aviso: Não foi possível buscar o CPF do cliente para nomear o arquivo: {e}")

            # Monta nome único para o arquivo no Storage
            timestamp = int(time.time())
            extensao = original_filename.split('.')[-1].lower() if '.' in original_filename else 'bin'
            storage_filename = f"{cliente_cpf}_{venda_id}_{timestamp}.{extensao}"
            print(f"Nome no Storage: {storage_filename}")

            # Pega nome do bucket dos Secrets
            bucket_name = os.environ.get("SUPABASE_COMPROVANTES_BUCKET")
            if not bucket_name:
                raise ValueError("Variável de ambiente SUPABASE_COMPROVANTES_BUCKET não configurada!")

            print(f"Bucket: {bucket_name}")
            print("⬆️ Fazendo upload...")

            # Faz o upload para o Supabase Storage
            storage_response = supabase.storage.from_(bucket_name).upload(
                path=storage_filename,
                file=file_bytes,
                file_options={
                    "content-type": file_type,
                    "cache-control": "3600",
                    "upsert": "true"
                }
            )
            print(f"✅ Upload concluído! Resposta: {storage_response}")

            # Pega a URL pública do arquivo recém-enviado
            public_url_response = supabase.storage.from_(bucket_name).get_public_url(storage_filename)
            comprovante_url = public_url_response
            print(f"🔗 URL Pública: {comprovante_url}")

            # Atualiza a tabela 'vendas' com a URL do comprovante
            print(f"💾 Atualizando tabela 'vendas' com a URL...")
            update_response = supabase.table('vendas').update({
                'comprovante_url': comprovante_url
            }).eq('id', venda_id).execute()

            if not update_response.data:
                 print(f"⚠️ Aviso: A atualização da URL do comprovante para venda {venda_id} não retornou dados.")

            print(f"✅ Venda atualizada!")

            # Limpa o estado e fecha o modal
            venda_id_para_comprovante.set(None)

            # Atualiza a lista de compras para mostrar "Comprovante Enviado"
            minhas_compras_trigger.set(minhas_compras_trigger() + 1)
            
            # Dispara triggers de atualização
            cashback_trigger.set(cashback_trigger() + 1)
            cashback_aguardando_trigger.set(cashback_aguardando_trigger() + 1)

            # ========== MODAL DE SUCESSO ATRAENTE (VERSÃO COMPACTA) ==========
            modal_sucesso_html = f'''
            <div id="modal_sucesso_comprovante" style="
                position: fixed; top: 0; left: 0; width: 100%; height: 100%;
                background: rgba(0,0,0,0.9); z-index: 10002;
                display: flex; align-items: center; justify-content: center;
                animation: fadeIn 0.3s ease-in;
                overflow-y: auto;
                padding: 1rem;
            ">
                <div style="
                    background: linear-gradient(135deg, #10b981 0%, #059669 100%);
                    border-radius: 1.5rem; padding: 2rem;
                    max-width: 95%; width: 500px;
                    max-height: 90vh;
                    overflow-y: auto;
                    text-align: center; 
                    box-shadow: 0 20px 60px rgba(0,0,0,0.5);
                    animation: slideUp 0.5s ease-out;
                    color: white;
                    margin: auto;
                " onclick="event.stopPropagation()">
                    
                    <!-- Ícone animado -->
                    <div style="
                        width: 80px; height: 80px;
                        margin: 0 auto 1rem auto;
                        background: rgba(255,255,255,0.2);
                        border-radius: 50%;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        animation: pulse 2s infinite;
                    ">
                        <span style="font-size: 3rem;">✅</span>
                    </div>
                    
                    <!-- Título -->
                    <h2 style="
                        margin: 0 0 0.5rem 0;
                        font-size: 1.5rem;
                        font-weight: 800;
                        text-shadow: 0 2px 4px rgba(0,0,0,0.2);
                    ">Comprovante Enviado!</h2>
                    
                    <p style="
                        font-size: 0.95rem;
                        margin: 0 0 1.5rem 0;
                        opacity: 0.95;
                    ">Recebido com sucesso!</p>
                    
                    <!-- Card de Informações COMPACTO -->
                    <div style="
                        background: rgba(255,255,255,0.15);
                        backdrop-filter: blur(10px);
                        border-radius: 1rem;
                        padding: 1.5rem;
                        margin: 1.5rem 0;
                        text-align: left;
                        border: 2px solid rgba(255,255,255,0.2);
                    ">
                        <h3 style="
                            margin: 0 0 1rem 0;
                            font-size: 1.1rem;
                            text-align: center;
                            font-weight: 700;
                        ">⏳ Próximos Passos</h3>
                        
                        <div style="margin-bottom: 1rem;">
                            <div style="display: flex; align-items: start; gap: 0.75rem;">
                                <span style="font-size: 1.5rem; min-width: 30px;">🔍</span>
                                <div>
                                    <h4 style="margin: 0 0 0.25rem 0; font-size: 0.95rem;">Aguarde Confirmação</h4>
                                    <p style="margin: 0; opacity: 0.9; font-size: 0.85rem;">
                                        Análise em até 24 horas.
                                    </p>
                                </div>
                            </div>
                        </div>
                        
                        <div style="margin-bottom: 1rem;">
                            <div style="display: flex; align-items: start; gap: 0.75rem;">
                                <span style="font-size: 1.5rem; min-width: 30px;">💰</span>
                                <div>
                                    <h4 style="margin: 0 0 0.25rem 0; font-size: 0.95rem;">Cashback via PIX</h4>
                                    <p style="margin: 0; opacity: 0.9; font-size: 0.85rem;">
                                        Receba em até <strong>2 dias úteis</strong>.
                                    </p>
                                </div>
                            </div>
                        </div>
                        
                        <div>
                            <div style="display: flex; align-items: start; gap: 0.75rem;">
                                <span style="font-size: 1.5rem; min-width: 30px;">📅</span>
                                <div>
                                    <h4 style="margin: 0 0 0.25rem 0; font-size: 0.95rem;">Agende seu Atendimento</h4>
                                    <p style="margin: 0; opacity: 0.9; font-size: 0.85rem;">
                                        Prazo: <strong>30 dias</strong> na clínica.
                                    </p>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Alerta COMPACTO -->
                    <div style="
                        background: rgba(255,255,255,0.25);
                        border-radius: 0.5rem;
                        padding: 0.75rem;
                        margin: 1rem 0;
                        font-size: 0.85rem;
                    ">
                        💡 Entre em contato com a clínica para agendar!
                    </div>
                    
                    <!-- Botão -->
                    <button onclick="document.getElementById('modal_sucesso_comprovante').remove()" style="
                        background: white;
                        color: #059669;
                        border: none;
                        padding: 0.875rem 2.5rem;
                        border-radius: 0.75rem;
                        font-weight: 700;
                        font-size: 1rem;
                        cursor: pointer;
                        transition: all 0.3s;
                        box-shadow: 0 4px 12px rgba(0,0,0,0.2);
                        margin-top: 0.5rem;
                        width: 100%;
                    " onmouseover="this.style.transform='scale(1.02)'; this.style.boxShadow='0 6px 20px rgba(0,0,0,0.3)';" 
                       onmouseout="this.style.transform='scale(1)'; this.style.boxShadow='0 4px 12px rgba(0,0,0,0.2)';">
                        Entendi! 👍
                    </button>
                </div>
            </div>
            
            <style>
                @keyframes fadeIn {{
                    from {{ opacity: 0; }}
                    to {{ opacity: 1; }}
                }}
                
                @keyframes slideUp {{
                    from {{ 
                        transform: translateY(50px);
                        opacity: 0;
                    }}
                    to {{ 
                        transform: translateY(0);
                        opacity: 1;
                    }}
                }}
                
                @keyframes pulse {{
                    0%, 100% {{ transform: scale(1); }}
                    50% {{ transform: scale(1.1); }}
                }}
            </style>
            '''
            
            # Injeta o modal na página
            ui.insert_ui(
                selector="body",
                where="beforeEnd",
                ui=ui.HTML(modal_sucesso_html)
            )
            # ===============================================

        except Exception as e:
            print(f"❌ Erro em _processar_envio_comprovante: {e}")
            import traceback
            traceback.print_exc()
            ui.notification_show(f"❌ Erro ao enviar comprovante: {str(e)}", type="error")

# ========== 9. CLIENTE INFORMA QUE PAGAMENTO FOI REALIZADO (ATUALIZANDO STATUS) ==========
    @reactive.Effect
    @reactive.event(input.informar_pagamento_id)
    def _monitor_informar_pagamento_id():
        """Atualiza o status quando o cliente clica em 'Informar Pagamento Realizado'"""
        try:
            venda_id = None
            try:
                venda_id = input.informar_pagamento_id()
            except:
                return

            if not venda_id or not supabase:
                return

            print(f"\n✅ CLIENTE INFORMOU PAGAMENTO - DEBUG")
            print(f"Venda ID: {venda_id}")

            # Busca a venda para garantir que ainda está pendente
            venda_check = supabase.table('vendas').select('pagamento_informado, numero_venda, status').eq('id', venda_id).single().execute() # Adicionado 'status'

            if not venda_check.data:
                ui.notification_show("❌ Venda não encontrada ao informar pagamento!", type="error")
                return

            # Verifica se já está informado OU se o status já não é mais 'aguardando_pagamento'
            if venda_check.data.get('pagamento_informado') or venda_check.data.get('status') != 'aguardando_pagamento':
                ui.notification_show("ℹ️ Pagamento já havia sido informado ou status inválido.", type="info")
                minhas_compras_trigger.set(minhas_compras_trigger() + 1)
                return

            numero_venda = venda_check.data.get('numero_venda', 'N/A')

            # --- ATUALIZAÇÃO PRINCIPAL AQUI ---
            # Atualiza o status E o campo pagamento_informado
            update_response = supabase.table('vendas').update({
                'pagamento_informado': True,
                'data_pagamento_informado': datetime.now().isoformat(),
                'status': 'aguardando_confirmacao' # <-- NOVO STATUS DEFINIDO AQUI
            }).eq('id', venda_id).execute()
            # ------------------------------------

            if not update_response.data:
                 print(f"⚠️ Aviso: A atualização para informar pagamento da venda {venda_id} não retornou dados.")

            print(f"✅ Status 'pagamento_informado' atualizado para TRUE e 'status' para 'aguardando_confirmacao' para a venda {numero_venda}")

            # Dispara o trigger para atualizar a lista de compras na tela
            minhas_compras_trigger.set(minhas_compras_trigger() + 1)
            
            cashback_trigger.set(cashback_trigger() + 1)

            # Notifica o usuário
            ui.notification_show(
                f"✅ Pagamento informado para a compra {numero_venda}!\n"
                f"Agora, envie o comprovante clicando no botão 'Enviar Comprovante' para garantir seu cashback.",
                type="message",
                duration=15
            )

        except Exception as e:
            print(f"❌ Erro em _monitor_informar_pagamento_id: {e}")
            import traceback
            traceback.print_exc()
            ui.notification_show(f"❌ Erro ao informar pagamento: {str(e)}", type="error")


    # ========== 6. ESTATÃSTICAS DE CASHBACK (CLIENTE) ==========
    @output
    @render.text
    def stat_cashback_total_recebido():
        """Calcula total de cashback recebido pelo cliente"""
        try:
            # Adicionar trigger para forçar atualização
            _ = cashback_trigger()
            
            if not supabase:
                return "R$ 0,00"
            
            user = user_data()
            if not user or user.get('tipo_usuario') != 'cliente':
                return "R$ 0,00"
            
            # Primeiro busca o cliente_id da tabela clientes
            cliente_result = supabase.table('clientes').select('id').eq('usuario_id', user['id']).execute()
            
            if not cliente_result.data:
                print(f"⚠️ Cliente não encontrado para usuario_id: {user['id']}")
                return "R$ 0,00"
            
            cliente_id = cliente_result.data[0]['id']
            print(f"🔍 Cliente ID encontrado: {cliente_id}")
            
            # Busca cashback PAGO do cliente
            result = supabase.table('cashback_pagamentos').select(
                'valor'
            ).eq('cliente_id', cliente_id).eq('pago', True).execute()
            
            print(f"💰 Cashbacks pagos encontrados: {len(result.data) if result.data else 0}")
            
            if not result.data:
                return "R$ 0,00"
            
            total_recebido = sum([float(c.get('valor', 0) or 0) for c in result.data])
            
            print(f"✅ Total recebido: R$ {total_recebido:.2f}")
            
            return formatar_moeda(total_recebido)
            
        except Exception as e:
            print(f"❌ Erro em stat_cashback_total_recebido: {e}")
            import traceback
            traceback.print_exc()
            return "R$ 0,00"

 
    
    @output
    @render.text
    def stat_cashback_aguardando():
        """Calcula cashback aguardando pagamento DE VENDAS JÁ CONFIRMADAS"""
        try:
            _ = cashback_aguardando_trigger()
            
            if not supabase:
                print("❌ DEBUG: Supabase não conectado")
                return "R$ 0,00"
            
            user = user_data()
            if not user or user.get('tipo_usuario') != 'cliente':
                print(f"❌ DEBUG: Usuário inválido ou não é cliente. Tipo: {user.get('tipo_usuario') if user else 'None'}")
                return "R$ 0,00"
            
            print(f"\n{'='*60}")
            print(f"🔍 DEBUG - STAT CASHBACK AGUARDANDO")
            print(f"{'='*60}")
            print(f"Usuario ID: {user['id']}")
            print(f"Usuario Nome: {user.get('nome')}")
            
            # Busca cliente
            cliente_result = supabase.table('clientes').select('id').eq('usuario_id', user['id']).execute()
            if not cliente_result.data:
                print("❌ DEBUG: Cliente não encontrado na tabela clientes")
                return "R$ 0,00"
            
            cliente_id = cliente_result.data[0]['id']
            print(f"Cliente ID: {cliente_id}")
            
            # TESTE 1: Busca TODOS os cashbacks do cliente (sem filtro de pago)
            test1 = supabase.table('cashback_pagamentos').select('*').eq('cliente_id', cliente_id).execute()
            print(f"\n📊 TESTE 1 - Todos os cashbacks:")
            print(f"Total de registros: {len(test1.data) if test1.data else 0}")
            if test1.data:
                for cb in test1.data:
                    print(f"  - Valor: {cb.get('valor')} | Pago: {cb.get('pago')} | Venda ID: {cb.get('venda_id')}")
            
            # TESTE 2: Busca cashbacks NÃO PAGOS
            test2 = supabase.table('cashback_pagamentos').select('*').eq('cliente_id', cliente_id).eq('pago', False).execute()
            print(f"\n📊 TESTE 2 - Cashbacks NÃO pagos:")
            print(f"Total de registros: {len(test2.data) if test2.data else 0}")
            if test2.data:
                for cb in test2.data:
                    print(f"  - Valor: {cb.get('valor')} | Venda ID: {cb.get('venda_id')}")
            
            # TESTE 3: Busca com JOIN das vendas
            test3 = supabase.table('cashback_pagamentos').select(
                '*, vendas(numero_venda, pagamento_confirmado, pagamento_informado, status)'
            ).eq('cliente_id', cliente_id).eq('pago', False).execute()
            print(f"\n📊 TESTE 3 - Cashbacks com JOIN vendas:")
            print(f"Total de registros: {len(test3.data) if test3.data else 0}")
            if test3.data:
                for cb in test3.data:
                    venda_info = cb.get('vendas', {})
                    print(f"  - Valor: {cb.get('valor')}")
                    print(f"    Venda: {venda_info.get('numero_venda') if venda_info else 'N/A'}")
                    print(f"    Pag. Informado: {venda_info.get('pagamento_informado') if venda_info else 'N/A'}")
                    print(f"    Confirmado: {venda_info.get('pagamento_confirmado') if venda_info else 'N/A'}")
                    print(f"    Status: {venda_info.get('status') if venda_info else 'N/A'}")
            
            # CÁLCULO FINAL
            if not test3.data:
                print(f"\n❌ Nenhum cashback encontrado")
                print(f"{'='*60}\n")
                return "R$ 0,00"
            
# Filtra vendas onde:
            # 1. Cliente enviou comprovante OU admin já confirmou
            # 2. MAS o cashback ainda NÃO foi pago
            cashbacks_aguardando = [
                c for c in test3.data 
                if c.get('vendas') 
                and (
                    c.get('vendas', {}).get('pagamento_informado', False) or  # Cliente enviou comprovante
                    c.get('vendas', {}).get('pagamento_confirmado', False)    # Admin confirmou pagamento
                )
            ]
            
            print(f"\n📊 TESTE 4 - Cashbacks aguardando pagamento:")
            print(f"Total filtrado: {len(cashbacks_aguardando)}")
            
            if not cashbacks_aguardando:
                print(f"❌ Nenhum cashback aguardando")
                print(f"{'='*60}\n")
                return "R$ 0,00"
            
            total_aguardando = sum([float(c.get('valor', 0) or 0) for c in cashbacks_aguardando])
            
            print(f"\n✅ TOTAL AGUARDANDO: R$ {total_aguardando:.2f}")
            print(f"{'='*60}\n")
            
            return formatar_moeda(total_aguardando)
            
        except Exception as e:
            print(f"❌ ERRO em stat_cashback_aguardando: {e}")
            import traceback
            traceback.print_exc()
            return "R$ 0,00"

    @output
    @render.ui
    def mensagem_status_cashback():
        """Mostra mensagem de status do cashback aguardando"""
        try:
            _ = cashback_aguardando_trigger()
            
            if not supabase:
                return ui.div()
            
            user = user_data()
            if not user or user.get('tipo_usuario') != 'cliente':
                return ui.div()
            
            # Busca cliente_id
            cliente_result = supabase.table('clientes').select('id').eq('usuario_id', user['id']).execute()
            if not cliente_result.data:
                return ui.div()
            
            cliente_id = cliente_result.data[0]['id']
            
            # Busca cashbacks aguardando com dados da venda
            result = supabase.table('cashback_pagamentos').select(
                '*, vendas(pagamento_informado, pagamento_confirmado)'
            ).eq('cliente_id', cliente_id).eq('pago', False).execute()
            
            if not result.data:
                return ui.div()
            
            # Verifica se algum já foi confirmado
            tem_confirmado = any([
                c.get('vendas', {}).get('pagamento_confirmado', False) 
                for c in result.data 
                if c.get('vendas')
            ])
            
            if tem_confirmado:
                # Pagamento confirmado pelo admin
                return ui.div(
                    {"style": "background: linear-gradient(135deg, #10b981, #059669); color: white; padding: 1rem; border-radius: 0.5rem; margin-top: 0.5rem; text-align: center;"},
                    ui.p(
                        {"style": "margin: 0; font-weight: 600; font-size: 1rem;"},
                        "✅ Seu pagamento foi confirmado!"
                    ),
                    ui.p(
                        {"style": "margin: 0.5rem 0 0 0; font-size: 0.9rem; opacity: 0.95;"},
                        "💰 O PIX será creditado em até 2 dias úteis"
                    )
                )
            else:
                # Apenas aguardando confirmação
                return ui.div(
                    {"style": "background: linear-gradient(135deg, #f59e0b, #d97706); color: white; padding: 1rem; border-radius: 0.5rem; margin-top: 0.5rem; text-align: center;"},
                    ui.p(
                        {"style": "margin: 0; font-weight: 600; font-size: 1rem;"},
                        "⏳ Aguardando Confirmação"
                    ),
                    ui.p(
                        {"style": "margin: 0.5rem 0 0 0; font-size: 0.9rem; opacity: 0.95;"},
                        "Estamos analisando seu comprovante"
                    )
                )
            
        except Exception as e:
            print(f"❌ Erro em mensagem_status_cashback: {e}")
            return ui.div()
            
    # ========== 7. LISTA DE CASHBACK (CLIENTE) ==========
    @output
    @render.ui
    def lista_cashback_cliente():
        """Lista histórico de cashback do cliente (apenas de vendas confirmadas)"""
        try:
            _ = cashback_trigger()
            
            user = user_data()
            if not user or not supabase:
                return ui.div()
            
            if user.get('tipo_usuario') != 'cliente':
                return ui.div()
            
            # Busca cliente pelo usuario_id
            cliente_result = supabase.table('clientes').select('id').eq('usuario_id', user['id']).execute()
            
            if not cliente_result.data:
                return ui.div(
                    {"style": "text-align: center; padding: 3rem; color: #94a3b8;"},
                    ui.h5("📭 Nenhum cashback registrado"),
                    ui.p("Seus cashbacks aparecerão aqui após suas compras serem confirmadas")
                )
            
            cliente_id = cliente_result.data[0]['id']
            
            # Busca cashbacks do cliente (apenas de vendas confirmadas)
            result = supabase.table('cashback_pagamentos').select(
                '*, vendas!inner(numero_venda, criado_em, pagamento_confirmado)'
            ).eq('cliente_id', cliente_id).order('criado_em', desc=True).execute()
            
            if not result.data:
                return ui.div(
                    {"style": "text-align: center; padding: 3rem; color: #94a3b8;"},
                    ui.h5("📭 Nenhum cashback registrado"),
                    ui.p("Seus cashbacks aparecerão aqui após suas compras serem confirmadas")
                )
            
            # Filtra apenas vendas confirmadas
            cashbacks_confirmados = [
                c for c in result.data 
                if c.get('vendas', {}).get('pagamento_confirmado', False)
            ]
            
            if not cashbacks_confirmados:
                return ui.div(
                    {"style": "text-align: center; padding: 3rem; color: #94a3b8;"},
                    ui.h5("📭 Nenhum cashback confirmado"),
                    ui.p("Aguardando confirmação dos pagamentos...")
                )
            
            cards = []
            for cashback in cashbacks_confirmados:
                pago = cashback.get('pago', False)
                cor_border = "#10b981" if pago else "#f59e0b"
                cor_status = "#10b981" if pago else "#f59e0b"
                status = "✅ Pago" if pago else "⏳ Aguardando"
                
                venda = cashback.get('vendas', {})
                numero_venda = venda.get('numero_venda', 'N/A')
                data_venda = venda.get('criado_em')
                data_pagamento = cashback.get('data_pagamento')
                percentual = cashback.get('percentual', 0)
                nivel = cashback.get('nivel', 1)
                
                # Nome do nível
                if nivel == 3:
                    nome_nivel = "💎 DIAMANTE"
                elif nivel == 2:
                    nome_nivel = "🥇 OURO"
                else:
                    nome_nivel = "🥈 PRATA"
                
                card = ui.div(
                    {"class": "card-custom", "style": f"margin-bottom: 1rem; border-left: 4px solid {cor_border};"},
                    ui.row(
                        ui.column(8,
                            ui.h6(f"🛒 Venda: {numero_venda}", style="margin: 0 0 0.5rem 0;"),
                            ui.p(f"📅 Compra: {pd.to_datetime(data_venda).strftime('%d/%m/%Y') if data_venda else '-'}", 
                                 style="margin: 0.25rem 0; font-size: 0.9rem; color: #546E7A;"),
                            ui.p(f"💰 Valor: {formatar_moeda(cashback.get('valor', 0))}", 
                                 style="margin: 0.25rem 0; font-weight: 700; color: #10b981; font-size: 1.1rem;"),
                            ui.p(f"🎯 {nome_nivel} ({percentual}%)", 
                                 style="margin: 0.25rem 0; font-size: 0.85rem; color: #546E7A; font-weight: 600;")
                        ),
                        ui.column(4,
                            ui.div(
                                {"style": "text-align: right;"},
                                ui.h6(status, style=f"margin: 0 0 0.5rem 0; font-weight: 600; color: {cor_status};"),
                                ui.p(f"💳 {pd.to_datetime(data_pagamento).strftime('%d/%m/%Y') if data_pagamento else 'Em processamento'}", 
                                     style="margin: 0; font-size: 0.85rem; color: #546E7A;")
                            )
                        )
                    )
                )
                cards.append(card)
            
            return ui.div(*cards)
            
        except Exception as e:
            print(f"❌ Erro em lista_cashback_cliente: {e}")
            import traceback
            traceback.print_exc()
            return ui.div(
                {"style": "text-align: center; padding: 2rem;"},
                ui.p("Erro ao carregar histórico de cashback", style="color: #ef4444;")
            )
        
                   
    # ========== EFFECT PARA TOGGLE ATIVO/INATIVO ==========
    @reactive.Effect
    def _monitor_toggle_usuario():
        """Ativa/desativa usuário"""
        try:
            usuario_id = None
            try:
                usuario_id = input.toggle_usuario_id()
            except:
                return
            
            if not usuario_id or not supabase:
                return
            
            print(f"🔄 Toggle usuário: {usuario_id}")
            
            result = supabase.table('usuarios').select('ativo, nome').eq('id', usuario_id).execute()
            
            if not result.data:
                return
            
            usuario = result.data[0]
            novo_status = not usuario.get('ativo', True)
            
            supabase.table('usuarios').update({'ativo': novo_status}).eq('id', usuario_id).execute()
            
            ui.notification_show(
                f"{'✅ Ativado' if novo_status else '⏸️ Desativado'}: {usuario['nome']}",
                type="message",
                duration=3
            )
            
        except Exception as e:
            print(f"❌ Erro _monitor_toggle_usuario: {e}")
            ui.notification_show(f"❌ Erro: {str(e)}", type="error")

    @reactive.Effect
    def _monitor_toggle_clinica():
        """Ativa/desativa clínica"""
        try:
            clinica_id = None
            try:
                clinica_id = input.toggle_clinica_id()
            except:
                return
            
            if not clinica_id or not supabase:
                return
            
            print(f"🔄 Toggle clínica: {clinica_id}")
            
            result = supabase.table('clinicas').select('ativo, razao_social').eq('id', clinica_id).execute()
            
            if not result.data:
                return
            
            clinica = result.data[0]
            novo_status = not clinica.get('ativo', True)
            
            supabase.table('clinicas').update({'ativo': novo_status}).eq('id', clinica_id).execute()
            
            ui.notification_show(
                f"{'✅ Ativada' if novo_status else '⏸️ Desativada'}: {clinica['razao_social']}",
                type="message",
                duration=3
            )
            
        except Exception as e:
            print(f"❌ Erro _monitor_toggle_clinica: {e}")
            ui.notification_show(f"❌ Erro: {str(e)}", type="error")


    @reactive.Effect
    def _monitor_ver_clinica():
        """Mostra modal com detalhes completos da clínica"""
        try:
            clinica_id = None
            try:
                clinica_id = input.ver_clinica_id()
            except:
                return
            
            if not clinica_id or not supabase:
                return
            
            # Busca clínica completa
            result = supabase.table('clinicas').select('*').eq('id', clinica_id).execute()
            
            if not result.data:
                ui.notification_show("❌ Clínica não encontrada!", type="error")
                return
            
            clinica = result.data[0]
            
            # Busca comissão
            comissao_result = supabase.table('comissoes_clinica').select('*').eq('clinica_id', clinica_id).execute()
            comissao_info = "Não configurada"
            if comissao_result.data:
                com = comissao_result.data[0]
                if com.get('tipo') == 'percentual':
                    comissao_info = f"{com.get('valor_percentual', 0)}%"
                else:
                    comissao_info = formatar_moeda(com.get('valor_fixo', 0))
            
            # Dados PIX
            pix_info = "Não cadastrado"
            try:
                dados_pix = json.loads(clinica.get('dados_pix', '{}'))
                if dados_pix.get('chave'):
                    pix_info = f"{dados_pix.get('chave')} ({dados_pix.get('tipo', 'N/A')})"
            except:
                pass
            
            # Remove modal anterior
            ui.remove_ui(selector=f"#ver_clinica_modal_{clinica_id}")
            
            modal_html = f'''
            <div id="ver_clinica_modal_{clinica_id}" style="
                position: fixed; top: 0; left: 0; width: 100%; height: 100%;
                background: rgba(0,0,0,0.8); z-index: 9999;
                display: flex; align-items: center; justify-content: center;
                overflow-y: auto; padding: 2rem;
            ">
                <div style="
                    background: white; border-radius: 1rem; padding: 2rem;
                    max-width: 800px; width: 100%;
                " onclick="event.stopPropagation()">
                    <h3 style="color: #1DD1A1; margin-bottom: 1.5rem;">🏥 Detalhes da Clínica</h3>
                    
                    <div style="background: #f8fafc; padding: 1rem; border-radius: 0.5rem; margin-bottom: 1rem;">
                        <h5 style="margin: 0 0 0.5rem 0;">📋 Dados Principais</h5>
                        <p style="margin: 0.25rem 0;"><strong>Razão Social:</strong> {clinica.get('razao_social', 'N/A')}</p>
                        <p style="margin: 0.25rem 0;"><strong>Nome Fantasia:</strong> {clinica.get('nome_fantasia', '-')}</p>
                        <p style="margin: 0.25rem 0;"><strong>CNPJ:</strong> {formatar_cnpj(clinica.get('cnpj', ''))}</p>
                        <p style="margin: 0.25rem 0;"><strong>Email:</strong> {clinica.get('email', '-')}</p>
                        <p style="margin: 0.25rem 0;"><strong>Telefone:</strong> {formatar_whatsapp(clinica.get('telefone', '-'))}</p>
                        <p style="margin: 0.25rem 0;"><strong>WhatsApp:</strong> {formatar_whatsapp(clinica.get('whatsapp', '-'))}</p>
                    </div>
                    
                    <div style="background: #f0f9ff; padding: 1rem; border-radius: 0.5rem; margin-bottom: 1rem;">
                        <h5 style="margin: 0 0 0.5rem 0;">📍 Endereço</h5>
                        <p style="margin: 0.25rem 0;">{clinica.get('endereco_rua', '-')}</p>
                        <p style="margin: 0.25rem 0;">{clinica.get('endereco_cidade', '-')}/{clinica.get('endereco_estado', '-')}</p>
                    </div>
                    
                    <div style="background: #ecfdf5; padding: 1rem; border-radius: 0.5rem; margin-bottom: 1rem;">
                        <h5 style="margin: 0 0 0.5rem 0;">👤 Responsável</h5>
                        <p style="margin: 0.25rem 0;"><strong>Nome:</strong> {clinica.get('responsavel_nome', '-')}</p>
                        <p style="margin: 0.25rem 0;"><strong>Contato:</strong> {clinica.get('responsavel_contato', '-')}</p>
                    </div>
                    
                    <div style="background: #fef3c7; padding: 1rem; border-radius: 0.5rem; margin-bottom: 1rem;">
                        <h5 style="margin: 0 0 0.5rem 0;">💰 Financeiro</h5>
                        <p style="margin: 0.25rem 0;"><strong>Comissão:</strong> {comissao_info}</p>
                        <p style="margin: 0.25rem 0;"><strong>PIX:</strong> {pix_info}</p>
                    </div>
                    
                    <button onclick="document.getElementById('ver_clinica_modal_{clinica_id}').remove()" 
                        style="
                            width: 100%; background: #1DD1A1; color: white; border: none;
                            padding: 0.75rem; border-radius: 0.5rem; font-weight: 600;
                            cursor: pointer; margin-top: 1rem;
                        ">✅ Fechar</button>
                </div>
            </div>
            '''
            
            ui.insert_ui(
                selector="body",
                where="beforeEnd",
                ui=ui.HTML(modal_html)
            )
            
        except Exception as e:
            print(f"Erro _monitor_ver_clinica: {e}")
            import traceback
            traceback.print_exc()
            ui.notification_show(f"❌ Erro: {str(e)}", type="error")
    ## CONTABILIDADE
    
## CONTABILIDADE
    
    def obter_periodo_contabil():
        """Retorna tupla (data_inicio, data_fim) baseado no filtro selecionado"""
        try:
            periodo = input.periodo_contabil()
            hoje = date.today()
            
            if periodo == "mes_atual":
                data_inicio = hoje.replace(day=1)
                data_fim = hoje
            elif periodo == "mes_anterior":
                # Último dia do mês anterior
                primeiro_dia_mes_atual = hoje.replace(day=1)
                ultimo_dia_mes_anterior = primeiro_dia_mes_atual - pd.Timedelta(days=1)
                data_inicio = ultimo_dia_mes_anterior.replace(day=1)
                data_fim = ultimo_dia_mes_anterior
            elif periodo == "trimestre":
                data_inicio = hoje - pd.Timedelta(days=90)
                data_fim = hoje
            elif periodo == "ano":
                data_inicio = hoje.replace(month=1, day=1)
                data_fim = hoje
            elif periodo == "tudo":
                return None, None
            else:
                # Usa as datas customizadas
                data_inicio = input.data_inicio_contabil()
                data_fim = input.data_fim_contabil()
            
            return data_inicio, data_fim
        except Exception as e:
            print(f"Erro obter_periodo_contabil: {e}")
            return None, None

# ===================================================================
    # === 🏥 INÍCIO - LÓGICA DA NOVA ABA "CLÍNICAS PARCEIRAS" ===
    # ===================================================================

    @output
    @render.ui
    def view_clinicas_cliente():
        """
        Controlador principal da view.
        Mostra a lista de clínicas ou a página de detalhes de uma clínica.
        """
        clinica_id = cliente_viu_clinica_id()
        
        if clinica_id is None:
            # --- VIEW 1: MOSTRA A LISTA DE CLÍNICAS ---
            return ui.div(
                ui.input_text("buscar_clinica_cliente", "🔍 Buscar Clínica por Nome ou Cidade", 
                              placeholder="Digite o nome ou cidade..."),
                ui.hr(),
                ui.output_ui("lista_clinicas_para_clientes")
            )
        else:
            # --- VIEW 2: MOSTRA A PÁGINA DE DETALHES DA CLÍNICA ---
            return ui.output_ui("detalhe_clinica_cliente_page")

    @reactive.Effect
    @reactive.event(input.selecionar_clinica_id)
    def _selecionar_clinica():
        """Define a clínica que o cliente quer ver."""
        try:
            clinica_id = input.selecionar_clinica_id()
            if clinica_id:
                print(f"Cliente está vendo a clínica ID: {clinica_id}")
                cliente_viu_clinica_id.set(clinica_id)
        except Exception as e:
            print(f"Erro ao selecionar clínica: {e}")

    @reactive.Effect
    @reactive.event(input.voltar_para_lista_clinicas)
    def _voltar_lista_clinicas():
        """Volta para a lista de clínicas."""
        print("Cliente voltou para a lista de clínicas.")
        cliente_viu_clinica_id.set(None)

    @output
    @render.ui
    def lista_clinicas_para_clientes():
        """Renderiza os cards da lista de clínicas."""
        try:
            if not supabase: return ui.div("Erro de conexão.")
            
            # Busca clínicas ativas
            query = supabase.table('clinicas').select('*').eq('ativo', True)
            
            # Filtro de busca
            busca = input.buscar_clinica_cliente()
            if busca:
                query = query.or_(
                    f'nome_fantasia.ilike.%{busca}%,razao_social.ilike.%{busca}%,endereco_cidade.ilike.%{busca}%'
                )
            
            result = query.order('nome_fantasia').execute()

            if not result.data:
                return ui.div(
                    {"style": "text-align: center; padding: 3rem; color: #94a3b8;"},
                    ui.h5("Nenhuma clínica encontrada")
                )

            cards = []
            for clinica in result.data:
                clinica_id = str(clinica['id'])
                nome = clinica.get('nome_fantasia') or clinica.get('razao_social', 'N/A')
                cidade = clinica.get('endereco_cidade', '')
                estado = clinica.get('endereco_estado', '')
                rua = clinica.get('endereco_rua', '')
                
                # Conta quantos procedimentos
                procs_count_res = supabase.table('procedimentos').select('id', count='exact').eq('clinica_id', clinica_id).eq('ativo', True).execute()
                pacotes_count_res = supabase.table('pacotes').select('id', count='exact').eq('clinica_id', clinica_id).eq('ativo', True).execute()
                
                total_procs = procs_count_res.count or 0
                total_pacotes = pacotes_count_res.count or 0
                
                card = ui.div(
                    {"class": "card-custom", "style": "margin-bottom: 1rem; border-left: 4px solid #1DD1A1;"},
                    ui.row(
                        ui.column(8,
                            ui.h5(f"🏥 {nome}", style="margin: 0 0 0.5rem 0;"),
                            ui.p(f"📍 {rua} - {cidade}/{estado}", style="margin: 0.25rem 0; font-size: 0.9rem; color: #546E7A;"),
                            ui.p(f"🔬 {total_procs} procedimentos | 🎁 {total_pacotes} pacotes", 
                                 style="margin: 0.5rem 0 0 0; font-size: 0.9rem; color: #10b981; font-weight: 600;")
                        ),
                        ui.column(4,
                            ui.div(
                                {"style": "text-align: right; padding-top: 1rem;"},
                                ui.tags.button(
                                    "Ver Procedimentos",
                                    class_="btn btn-primary w-100",
                                    onclick=f"Shiny.setInputValue('selecionar_clinica_id', '{clinica_id}', {{priority: 'event'}})"
                                )
                            )
                        )
                    )
                )
                cards.append(card)
            
            return ui.div(*cards)
        
        except Exception as e:
            print(f"Erro em lista_clinicas_para_clientes: {e}")
            return ui.div({"class": "alert alert-danger"}, f"Erro ao listar clínicas: {e}")

    @output
    @render.ui
    def detalhe_clinica_cliente_page():
        """Renderiza a página de detalhes (vitrine) de uma única clínica."""
        try:
            clinica_id = cliente_viu_clinica_id()
            if not clinica_id or not supabase:
                return ui.div("Erro.")
            
            # Busca dados da clínica
            clinica_res = supabase.table('clinicas').select('*').eq('id', clinica_id).maybe_single().execute()
            if not clinica_res.data:
                return ui.div("Clínica não encontrada.")
            
            clinica = clinica_res.data
            nome = clinica.get('nome_fantasia') or clinica.get('razao_social', 'N/A')
            cidade = clinica.get('endereco_cidade', '')
            estado = clinica.get('endereco_estado', '')
            rua = clinica.get('endereco_rua', '')
            
            return ui.div(
                # Botão Voltar
                ui.input_action_button("voltar_para_lista_clinicas", "← Voltar para todas as clínicas", 
                                       class_="btn btn-outline-secondary mb-3"),
                
                # Card de Informações da Clínica
                ui.div(
                    {"class": "card-custom", "style": "margin-bottom: 1.5rem; background: linear-gradient(135deg, #1DD1A1, #0D9488); color: white;"},
                    ui.h4(f"🏥 {nome}", style="color: white;"),
                    ui.p(f"📍 {rua} - {cidade}/{estado}")
                ),
                
                # Lista de Itens (Procedimentos e Pacotes)
                ui.h5("Procedimentos e Pacotes Disponíveis"),
                ui.output_ui("lista_itens_clinica_especifica") # Output separado para os itens
            )
            
        except Exception as e:
            print(f"Erro em detalhe_clinica_cliente_page: {e}")
            return ui.div({"class": "alert alert-danger"}, f"Erro ao carregar página da clínica: {e}")

    @output
    @render.ui
    def lista_itens_clinica_especifica():
        """Renderiza os cards de procedimentos e pacotes para a vitrine da clínica."""
        try:
            clinica_id = cliente_viu_clinica_id()
            if not clinica_id:
                return ui.div()
                
            # 1. Busca Procedimentos
            procs_res = supabase.table('procedimentos').select('*').eq('clinica_id', clinica_id).eq('ativo', True).order('nome').execute()
            
            # 2. Busca Pacotes
            pacotes_res = supabase.table('pacotes').select('*, pacotes_itens(procedimentos(nome))').eq('clinica_id', clinica_id).eq('ativo', True).order('nome').execute()
            
            # 3. Pega Nível de Cashback do Cliente
            user = user_data()
            cashback_perc_cliente = 4 # Padrão
            if user:
                try:
                    cliente_id_logado = cliente_logado.get()['id']
                    vendas_result = supabase.table('vendas').select('id', count='exact').eq('cliente_id', cliente_id_logado).eq('pagamento_confirmado', True).execute()
                    total_compras = vendas_result.count or 0
                    
                    if total_compras >= 26: cashback_perc_cliente = 7
                    elif total_compras >= 11: cashback_perc_cliente = 5.5
                except: pass
            
            cards = []

            # Renderiza Pacotes Primeiro (Destaque)
            if pacotes_res.data:
                for pacote in pacotes_res.data:
                    item_id_str = str(pacote['id'])
                    item_preco = float(pacote.get('valor_final', 0))
                    cashback_calculado = item_preco * (cashback_perc_cliente / 100)
                    
                    nomes_sub_itens = [item['procedimentos']['nome'] for item in pacote.get('pacotes_itens', []) if item.get('procedimentos')]
                    sub_itens_html = ", ".join(nomes_sub_itens)
                    
                    card_pacote = ui.div(
                        {"style": "background: linear-gradient(135deg, #f0f9ff, #e0f2fe); padding: 1rem; border-radius: 0.5rem; margin-bottom: 0.5rem; border: 2px solid #3b82f6;"},
                        ui.row(
                            ui.column(8,
                                ui.h6(f"🎁 {pacote.get('nome', 'N/A')}", style="margin: 0 0 0.5rem 0; color: #1e40af;"),
                                ui.p(f"💵 {formatar_moeda(item_preco)}", style="margin: 0; font-weight: 700; color: #1d4ed8; font-size: 1.1rem;"),
                                ui.p(f"💰 Cashback: {formatar_moeda(cashback_calculado)}", style="margin: 0.25rem 0 0 0; color: #10b981; font-size: 0.85rem;"),
                                ui.p(f"Inclui: {sub_itens_html}", style="margin: 0.5rem 0 0 0; font-size: 0.8rem; color: #546E7A; font-style: italic;")
                            ),
                            ui.column(4,
                                ui.div(
                                    {"style": "text-align: right; padding-top: 1rem;"},
                                    ui.tags.button(
                                        "🛒 Adicionar Pacote",
                                        class_="btn w-100",
                                        onclick=f"Shiny.setInputValue('add_carrinho_cliente', 'pacote:{item_id_str}', {{priority: 'event'}})",
                                        style="font-weight: 600; background: #3b82f6; color: white;"
                                    )
                                )
                            )
                        )
                    )
                    cards.append(card_pacote)

            # Renderiza Procedimentos
            if procs_res.data:
                for proc in procs_res.data:
                    item_id_str = str(proc['id'])
                    item_preco = float(proc.get('preco', 0))
                    cashback_calculado = item_preco * (cashback_perc_cliente / 100)
                    
                    card_proc = ui.div(
                        {"style": "background: #f8fafc; padding: 1rem; border-radius: 0.5rem; margin-bottom: 0.5rem; border: 2px solid #e2e8f0;"},
                        ui.row(
                            ui.column(8,
                                ui.h6(f"🔬 {proc.get('nome', 'N/A')}", style="margin: 0 0 0.5rem 0;"),
                                ui.p(f"💵 {formatar_moeda(item_preco)}", style="margin: 0; font-weight: 600; color: #1DD1A1; font-size: 1rem;"),
                                ui.p(f"💰 Cashback: {formatar_moeda(cashback_calculado)}", style="margin: 0.25rem 0 0 0; color: #10b981; font-size: 0.85rem;")
                            ),
                            ui.column(4,
                                ui.div(
                                    {"style": "text-align: right; padding-top: 0.5rem;"},
                                    ui.tags.button(
                                        "🛒 Adicionar",
                                        class_="btn btn-primary w-100",
                                        onclick=f"Shiny.setInputValue('add_carrinho_cliente', 'procedimento:{item_id_str}', {{priority: 'event'}})",
                                        style="font-weight: 600;"
                                    )
                                )
                            )
                        )
                    )
                    cards.append(card_proc)
            
            if not cards:
                return ui.div(
                    {"style": "text-align: center; padding: 3rem; color: #94a3b8;"},
                    ui.h5("Esta clínica ainda não cadastrou itens")
                )
                
            return ui.div(*cards)
            
        except Exception as e:
            print(f"Erro em lista_itens_clinica_especifica: {e}")
            return ui.div({"class": "alert alert-danger"}, f"Erro ao listar itens: {e}")

    # ===================================================================
    # === 🏥 FIM - LÓGICA DA NOVA ABA "CLÍNICAS PARCEIRAS" ===
    # ===================================================================
    
    # ===================================================================
    # === 📺 INÍCIO - LÓGICA DA VITRINE (SALA DE ESPERA) ===
    # ===================================================================

    @reactive.Effect
    def _carregar_dados_vitrine():
        """Carrega os dados salvos da vitrine no formulário."""
        try:
            user = user_data()
            if not user or not supabase:
                return

            # Busca clínica
            clinica_res = supabase.table('clinicas').select('id, vitrine_titulo, vitrine_mensagem, vitrine_banner_url').eq('usuario_id', user['id']).maybe_single().execute()
            
            if clinica_res.data:
                clinica = clinica_res.data
                # Atualiza os inputs
                ui.update_text("vitrine_titulo_input", value=clinica.get('vitrine_titulo') or "")
                ui.update_text_area("vitrine_mensagem_input", value=clinica.get('vitrine_mensagem') or "")
                
                # Atualiza a reativa que guarda a URL do banner
                vitrine_banner_url_reativa.set(clinica.get('vitrine_banner_url'))

        except Exception as e:
            print(f"Erro ao carregar dados da vitrine: {e}")

    # Reativa para guardar a URL do banner atual
    vitrine_banner_url_reativa = reactive.Value(None)

    @output
    @render.ui
    def vitrine_banner_preview():
        """Mostra a prévia do banner (novo ou salvo)."""
        file_info = input.vitrine_banner_input()
        url_salva = vitrine_banner_url_reativa()
        
        src = None
        
        if file_info:
            # --- Prévia do NOVO upload ---
            try:
                file = file_info[0]
                file_path = file['datapath']
                with open(file_path, 'rb') as f:
                    foto_bytes = f.read()
                    foto_base64 = base64.b64encode(foto_bytes).decode()
                src = f"data:image/jpeg;base64,{foto_base64}"
            except Exception as e:
                print(f"Erro ao ler prévia: {e}")
                return ui.div()
        elif url_salva:
            # --- Mostra imagem JÁ SALVA ---
            src = url_salva
        
        if src:
            return ui.div(
                {"style": "text-align: center; margin-top: 1rem;"},
                ui.p("Prévia do Banner:", style="font-weight: 600; margin: 0;"),
                ui.img(src=src, style="max-width: 100%; height: 150px; border-radius: 0.5rem; margin-top: 0.5rem; object-fit: cover;")
            )
        return ui.div()

    @reactive.effect
    @reactive.event(input.btn_salvar_vitrine_geral)
    def _salvar_vitrine_geral():
        """Salva configurações gerais da vitrine"""
        try:
            user = user_data()
            if not user or not supabase:
                return
            
            clinica_res = supabase.table('clinicas').select('id').eq('usuario_id', user['id']).maybe_single().execute()
            if not clinica_res.data:
                ui.notification_show("❌ Clínica não encontrada.", type="error")
                return
            
            clinica_id = clinica_res.data['id']
            
            # Dados para atualizar
            dados = {
                'vitrine_titulo': input.vitrine_titulo_input() or None,
                'vitrine_mensagem': input.vitrine_mensagem_input() or None
            }
            
            # Upload do banner se houver
            banner_file = input.vitrine_banner_input()
            if banner_file and len(banner_file) > 0:
                file_info = banner_file[0]
                file_content = file_info["datapath"]
                
                with open(file_content, 'rb') as f:
                    file_bytes = f.read()
                
                file_name = f"vitrine_banner_{clinica_id}_{int(time.time())}.jpg"
                
                upload_result = supabase.storage.from_('imagens').upload(
                    file_name,
                    file_bytes,
                    {"content-type": "image/jpeg", "upsert": "true"}
                )
                
                public_url = supabase.storage.from_('imagens').get_public_url(file_name)
                dados['vitrine_banner_url'] = public_url
            
            # Atualiza no banco
            supabase.table('clinicas').update(dados).eq('id', clinica_id).execute()
            
            ui.notification_show("✅ Configurações gerais salvas com sucesso!", type="success", duration=5)
            
        except Exception as e:
            print(f"❌ Erro ao salvar vitrine geral: {e}")
            import traceback
            traceback.print_exc()
            ui.notification_show(f"❌ Erro ao salvar: {str(e)}", type="error")
            
# ========== SALVAR CONFIGURAÇÕES DE PACOTES INDIVIDUAIS ==========
    @reactive.effect
    def _criar_handlers_pacotes_vitrine():
        """Cria handlers dinâmicos para salvar cada pacote"""
        try:
            user = user_data()
            if not user or not supabase:
                return
            
            clinica_res = supabase.table('clinicas').select('id').eq('usuario_id', user['id']).maybe_single().execute()
            if not clinica_res.data:
                return
            
            clinica_id = clinica_res.data['id']
            pacotes_res = supabase.table('pacotes').select('id').eq('clinica_id', clinica_id).eq('ativo', True).execute()
            
            if not pacotes_res.data:
                return
            
            for pacote in pacotes_res.data:
                pacote_id = pacote['id']
                pacote_id_safe = pacote_id.replace('-', '_')  # Remove hífens para o Shiny
                
                # Cria um effect para cada botão de salvar pacote
                @reactive.effect
                @reactive.event(getattr(input, f"btn_salvar_vitrine_pacote_{pacote_id_safe}"))
                def _salvar_config_pacote(pid=pacote_id, pid_safe=pacote_id_safe):
                    """Salva configuração de um pacote específico"""
                    try:
                        # Busca valores dos inputs
                        descricao = getattr(input, f"vitrine_desc_pacote_{pid_safe}")()
                        destaque = getattr(input, f"vitrine_destaque_pacote_{pid_safe}")()
                        
                        dados = {
                            'vitrine_descricao': descricao or None,
                            'vitrine_destaque': destaque
                        }
                        
                        # Upload da imagem se houver
                        img_input = getattr(input, f"vitrine_img_pacote_{pid_safe}")()
                        if img_input and len(img_input) > 0:
                            file_info = img_input[0]
                            file_content = file_info["datapath"]
                            
                            with open(file_content, 'rb') as f:
                                file_bytes = f.read()
                            
                            file_name = f"pacote_{pid}_{int(time.time())}.jpg"
                            
                            supabase.storage.from_('imagens').upload(
                                file_name,
                                file_bytes,
                                {"content-type": "image/jpeg", "upsert": "true"}
                            )
                            
                            public_url = supabase.storage.from_('imagens').get_public_url(file_name)
                            dados['vitrine_imagem_url'] = public_url
                        
                        # Atualiza no banco
                        supabase.table('pacotes').update(dados).eq('id', pid).execute()
                        
                        ui.notification_show("✅ Pacote configurado com sucesso!", type="success", duration=4)
                        
                    except Exception as e:
                        print(f"❌ Erro ao salvar config do pacote {pid}: {e}")
                        ui.notification_show(f"❌ Erro: {str(e)}", type="error")
        
        except Exception as e:
            print(f"❌ Erro ao criar handlers: {e}")

    @output
    @render.ui
    def vitrine_qr_code_display():
        """Gera e exibe o QR Code e o link para a vitrine pública."""
        try:
            user = user_data()
            if not user or not supabase:
                return ui.div()
                
            clinica_res = supabase.table('clinicas').select('id').eq('usuario_id', user['id']).maybe_single().execute()
            if not clinica_res.data:
                return ui.div()
            
            clinica_id = clinica_res.data['id']
            
# === Constrói a URL Base ===
            try:
                # Tenta obter do request do Shiny
                from starlette.requests import Request
                request: Request = session.http_conn.request
                base_url = str(request.base_url).rstrip('/')
                
                print(f"✅ URL obtida: {base_url}")
                
            except Exception as e:
                print(f"⚠️ Não foi possível obter URL automaticamente. Erro: {e}")

                # SUBSTITUA PELA SUA URL REAL se não estiver no HF
                base_url = "https://medpix.onrender.com"  # Substitua pela SUA URL do Render
                print(f"ℹ️ Usando URL fallback: {base_url}")

            # Link final
            public_link = f"{base_url}?view=vitrine&clinic_id={clinica_id}"
            
            # Gera QR Code
            qr_base64 = gerar_qr_code(public_link)
            
            return ui.div(
                {"style": "text-align: center;"},
                ui.img(src=f"data:image/png;base64,{qr_base64}", 
                       style="width: 250px; height: 250px; border: 5px solid #1DD1A1; border-radius: 0.5rem;"),
                
                ui.p("Link da sua vitrine:", style="margin-top: 1rem; font-weight: 600;"),
                ui.tags.input(
                    type="text",
                    value=public_link,
                    readonly=True,
                    style="width: 100%; padding: 0.5rem; border-radius: 0.25rem; border: 1px solid #ccc; text-align: center;"
                ),
                ui.p("Clique com o botão direito no QR Code para salvar e imprimir.", 
                     style="margin-top: 0.5rem; font-size: 0.9rem; color: #546E7A;")
            )
            
        except Exception as e:
            print(f"Erro ao gerar QR Code: {e}")
            return ui.div({"class": "alert alert-danger"}, f"Erro ao gerar QR Code: {e}")

    @output
    @render.ui
    def lista_pacotes_vitrine_config():
        """Lista pacotes para configuração individual na vitrine"""
        try:
            user = user_data()
            if not user or not supabase:
                return ui.div()
            
            # Busca clínica
            clinica_res = supabase.table('clinicas').select('id').eq('usuario_id', user['id']).maybe_single().execute()
            if not clinica_res.data:
                return ui.div({"class": "alert alert-info"}, "ℹ️ Nenhuma clínica encontrada.")
            
            clinica_id = clinica_res.data['id']
            
            # Busca pacotes ativos
            pacotes_res = supabase.table('pacotes').select('*').eq('clinica_id', clinica_id).eq('ativo', True).order('nome').execute()
            
            if not pacotes_res.data:
                return ui.div(
                    {"class": "alert alert-warning"},
                    "⚠️ Você ainda não tem pacotes cadastrados. Cadastre pacotes na aba 'Pacotes' primeiro!"
                )
            
            cards = []
            for pacote in pacotes_res.data:
                pacote_id = pacote['id']
                pacote_id_safe = pacote_id.replace('-', '_')
                nome = pacote.get('nome', 'Sem nome')
                preco = float(pacote.get('valor_final', 0))
                
                # Campos específicos para vitrine
                vitrine_imagem = pacote.get('vitrine_imagem_url', '')
                vitrine_descricao = pacote.get('vitrine_descricao', '')
                vitrine_destaque = pacote.get('vitrine_destaque', False)
                
                cards.append(
                    ui.div(
                        {"class": "card-custom", "style": f"margin-bottom: 1rem; border-left: 4px solid {'#f59e0b' if vitrine_destaque else '#cbd5e1'};"},
                        
                        ui.row(
                            ui.column(12,
                                ui.h6(f"📦 {nome}", style="color: #1e293b; margin-bottom: 0.5rem;"),
                                ui.p(f"Preço: {formatar_moeda(preco)}", style="color: #10b981; font-weight: 600; margin-bottom: 1rem;")
                            )
                        ),
                        
                        # Preview da imagem atual
                        ui.div(
                            ui.output_ui(f"preview_pacote_img_{pacote_id_safe}"),
                            style="margin-bottom: 1rem;"
                        ) if vitrine_imagem else ui.div(),
                        
                        # Upload de nova imagem
                        ui.input_file(
                            f"vitrine_img_pacote_{pacote_id_safe}",
                            "Imagem do Pacote (Recomendado: 800x600px)",
                            accept=[".png", ".jpg", ".jpeg", ".webp"],
                            button_label="📸 Carregar Imagem",
                            multiple=False
                        ),
                        
                        # Descrição motivacional
                        ui.input_text_area(
                            f"vitrine_desc_pacote_{pacote_id_safe}",
                            "Descrição Motivacional (para a vitrine)",
                            rows=3,
                            value=vitrine_descricao,
                            placeholder="Ex: Cuide da sua saúde! Este pacote inclui os exames essenciais para check-up completo."
                        ),
                        
                        # Checkbox de destaque
                        ui.input_checkbox(
                            f"vitrine_destaque_pacote_{pacote_id_safe}",
                            "⭐ Pacote em Destaque (aparece primeiro na vitrine)",
                            value=vitrine_destaque
                        ),
                        
                        ui.div(
                            {"style": "text-align: right; margin-top: 1rem;"},
                            ui.input_action_button(
                                f"btn_salvar_vitrine_pacote_{pacote_id_safe}",
                                "💾 Salvar Configurações deste Pacote",
                                class_="btn-success",
                                style="background: linear-gradient(135deg, #10b981, #059669); border: none; padding: 0.5rem 1.5rem;"
                            )
                        )
                    )
                )
            
            return ui.div(*cards)
            
        except Exception as e:
            print(f"❌ Erro ao listar pacotes para vitrine: {e}")
            import traceback
            traceback.print_exc()
            return ui.div({"class": "alert alert-danger"}, f"Erro: {e}")

    # ========== PREVIEW DAS IMAGENS DOS PACOTES ==========
    @output
    @render.ui
    def preview_pacote_img_():
        """Gera dinamicamente os previews das imagens dos pacotes"""
        # Esta função será chamada dinamicamente para cada pacote
        return ui.div()


    @output
    @render.text
    def contab_faturamento_total():
        try:
            if not supabase:
                return "R$ 0,00"
            
            # Busca datas
            data_inicio, data_fim = obter_periodo_contabil()
            
            query = supabase.table('vendas').select('valor_total').eq('tipo', 'venda').eq('pagamento_confirmado', True)
            
            if data_inicio:
                query = query.gte('criado_em', f'{data_inicio}T00:00:00')
            if data_fim:
                query = query.lte('criado_em', f'{data_fim}T23:59:59')
            
            result = query.execute()
            
            if not result.data:
                return "R$ 0,00"
            
            total = sum([float(v.get('valor_total', 0) or 0) for v in result.data])
            
            return formatar_moeda(total)
        except:
            return "R$ 0,00"


    @output
    @render.text
    def contab_comissoes_clinicas():
        try:
            if not supabase:
                return "R$ 0,00"
            
            data_inicio, data_fim = obter_periodo_contabil()
            
            query = supabase.table('vendas').select('*, itens_venda(*)').eq('tipo', 'venda').eq('pagamento_confirmado', True)
            
            if data_inicio:
                query = query.gte('criado_em', f'{data_inicio}T00:00:00')
            if data_fim:
                query = query.lte('criado_em', f'{data_fim}T23:59:59')
            
            result = query.execute()
            
            if not result.data:
                return "R$ 0,00"
            
            total_comissoes = 0
            
            for venda in result.data:
                # Só considera itens atendidos
                itens_atendidos = [item for item in venda.get('itens_venda', []) if item.get('atendido')]
                
                if not itens_atendidos:
                    continue
                
                clinica_id = venda.get('clinica_id')
                
                if not clinica_id:
                    continue
                
                # Busca comissão da clínica
                comissao_result = supabase.table('comissoes_clinica').select('*').eq('clinica_id', clinica_id).execute()
                
                if not comissao_result.data:
                    continue
                
                comissao_config = comissao_result.data[0]
                valor_atendimentos = sum([float(item.get('preco_total', 0) or 0) for item in itens_atendidos])
                
                # Calcula comissão
                if comissao_config.get('tipo') == 'percentual':
                    comissao = valor_atendimentos * (comissao_config.get('valor_percentual', 0) / 100)
                else:
                    comissao = comissao_config.get('valor_fixo', 0)
                
                total_comissoes += comissao
            
            return formatar_moeda(total_comissoes)
        except:
            return "R$ 0,00"


    @output
    @render.text
    def contab_lucro_liquido():
        """Calcula lucro da MedPIX: Faturamento - Pago às Clínicas - Cashback Pago"""
        try:
            if not supabase:
                return "R$ 0,00"
            
            data_inicio, data_fim = obter_periodo_contabil()
            
            # 1. FATURAMENTO TOTAL
            query_fat = supabase.table('vendas').select('valor_total').eq('pagamento_confirmado', True)
            
            if data_inicio:
                query_fat = query_fat.gte('criado_em', f'{data_inicio}T00:00:00')
            if data_fim:
                query_fat = query_fat.lte('criado_em', f'{data_fim}T23:59:59')
            
            result_fat = query_fat.execute()
            faturamento = sum([float(v.get('valor_total', 0) or 0) for v in (result_fat.data or [])])
            
            # 2. PAGO ÀS CLÍNICAS (parcelas pagas)
            query_vendas = supabase.table('vendas').select('*').eq('pagamento_confirmado', True)
            
            if data_inicio:
                query_vendas = query_vendas.gte('criado_em', f'{data_inicio}T00:00:00')
            if data_fim:
                query_vendas = query_vendas.lte('criado_em', f'{data_fim}T23:59:59')
            
            result_vendas = query_vendas.execute()
            
            comissoes_result = supabase.table('comissoes_clinica').select('*').execute()
            comissoes_por_clinica = {c['clinica_id']: c for c in (comissoes_result.data or [])}
            
            total_pago_clinicas = 0
            
            for venda in (result_vendas.data or []):
                clinica_id = venda.get('clinica_id')
                valor_venda = float(venda.get('valor_total', 0) or 0)
                
                comissao_config = comissoes_por_clinica.get(clinica_id, {})
                
                if comissao_config.get('tipo') == 'percentual':
                    percentual = float(comissao_config.get('valor_percentual', 0))
                    comissao_medpix = valor_venda * (percentual / 100)
                else:
                    comissao_medpix = float(comissao_config.get('valor_fixo', 0))
                
                valor_liquido = valor_venda - comissao_medpix
                valor_parcela = valor_liquido / 2
                
                # Conta apenas parcelas já pagas
                if venda.get('parcela1_clinica_paga', False):
                    total_pago_clinicas += valor_parcela
                
                if venda.get('parcela2_clinica_paga', False):
                    total_pago_clinicas += valor_parcela
            
            # 3. CASHBACK PAGO
            query_cashback = supabase.table('cashback_pagamentos').select('valor').eq('pago', True)
            
            if data_inicio:
                query_cashback = query_cashback.gte('data_pagamento', f'{data_inicio}T00:00:00')
            if data_fim:
                query_cashback = query_cashback.lte('data_pagamento', f'{data_fim}T23:59:59')
            
            result_cashback = query_cashback.execute()
            total_cashback = sum([float(c.get('valor', 0) or 0) for c in (result_cashback.data or [])])
            
            # LUCRO = Faturamento - Pago às Clínicas - Cashback
            lucro = faturamento - total_pago_clinicas - total_cashback
            
            print(f"\n💰 LUCRO MedPIX:")
            print(f"Faturamento: R$ {faturamento:.2f}")
            print(f"- Pago às Clínicas: R$ {total_pago_clinicas:.2f}")
            print(f"- Cashback Pago: R$ {total_cashback:.2f}")
            print(f"= Lucro MedPIX: R$ {lucro:.2f}\n")
            
            return formatar_moeda(lucro)
            
        except Exception as e:
            print(f"Erro contab_lucro_liquido: {e}")
            import traceback
            traceback.print_exc()
            return "R$ 0,00"


    @output
    @render.text
    def contab_cashback_pago():
        """Calcula total de cashback já pago aos clientes no período"""
        try:
            if not supabase:
                return "R$ 0,00"
            
            data_inicio, data_fim = obter_periodo_contabil()
            
            # Busca cashbacks pagos
            query = supabase.table('cashback_pagamentos').select('valor').eq('pago', True)
            
            if data_inicio:
                query = query.gte('data_pagamento', f'{data_inicio}T00:00:00')
            if data_fim:
                query = query.lte('data_pagamento', f'{data_fim}T23:59:59')
            
            result = query.execute()
            
            if not result.data:
                return "R$ 0,00"
            
            total = sum([float(c.get('valor', 0) or 0) for c in result.data])
            
            return formatar_moeda(total)
            
        except Exception as e:
            print(f"Erro contab_cashback_pago: {e}")
            return "R$ 0,00"


    @output
    @render.text
    def contab_pago_clinicas():
        """Calcula total já PAGO às clínicas (parcelas pagas)"""
        try:
            if not supabase:
                return "R$ 0,00"
            
            data_inicio, data_fim = obter_periodo_contabil()
            
            # Busca vendas com pagamento confirmado no período
            query = supabase.table('vendas').select('*').eq('pagamento_confirmado', True)
            
            if data_inicio:
                query = query.gte('criado_em', f'{data_inicio}T00:00:00')
            if data_fim:
                query = query.lte('criado_em', f'{data_fim}T23:59:59')
            
            result = query.execute()
            
            if not result.data:
                return "R$ 0,00"
            
            # Busca comissões de todas as clínicas
            comissoes_result = supabase.table('comissoes_clinica').select('*').execute()
            comissoes_por_clinica = {c['clinica_id']: c for c in (comissoes_result.data or [])}
            
            total_pago = 0
            
            for venda in result.data:
                clinica_id = venda.get('clinica_id')
                valor_venda = float(venda.get('valor_total', 0) or 0)
                
                # Calcula comissão Indiclin
                comissao_config = comissoes_por_clinica.get(clinica_id, {})
                
                if comissao_config.get('tipo') == 'percentual':
                    percentual = float(comissao_config.get('valor_percentual', 0))
                    comissao_medpix = valor_venda * (percentual / 100)
                else:
                    comissao_medpix = float(comissao_config.get('valor_fixo', 0))
                
                # Valor que vai para a clínica
                valor_liquido = valor_venda - comissao_medpix
                valor_parcela = valor_liquido / 2
                
                # Soma apenas parcelas JÁ PAGAS
                if venda.get('parcela1_clinica_paga', False):
                    total_pago += valor_parcela
                
                if venda.get('parcela2_clinica_paga', False):
                    total_pago += valor_parcela
            
            return formatar_moeda(total_pago)
            
        except Exception as e:
            print(f"Erro contab_pago_clinicas: {e}")
            import traceback
            traceback.print_exc()
            return "R$ 0,00"
            

    @output
    @render.ui
    def contab_resumo_geral():
        """Resumo financeiro do período com valores corretos"""
        try:
            if not supabase:
                return ui.div()
            
            data_inicio, data_fim = obter_periodo_contabil()
            
            # Busca vendas confirmadas do período
            query = supabase.table('vendas').select('*').eq('pagamento_confirmado', True)
            
            if data_inicio:
                query = query.gte('criado_em', f'{data_inicio}T00:00:00')
            if data_fim:
                query = query.lte('criado_em', f'{data_fim}T23:59:59')
            
            result = query.execute()
            
            if not result.data:
                return ui.div(
                    {"style": "text-align: center; padding: 3rem; color: #94a3b8;"},
                    ui.h5("📭 Nenhuma venda no período selecionado")
                )
            
            # ========== ESTATÍSTICAS BÁSICAS ==========
            total_vendas = len(result.data)
            clinicas_unicas = len(set([v['clinica_id'] for v in result.data if v.get('clinica_id')]))
            
            # Calcula ticket médio
            valores = [float(v.get('valor_total', 0) or 0) for v in result.data]
            ticket_medio = sum(valores) / len(valores) if valores else 0
            
            # ========== CALCULA VALORES FINANCEIROS ==========
            
            # 1. FATURAMENTO TOTAL
            faturamento_total = sum(valores)
            
            # 2. PAGO ÀS CLÍNICAS (apenas parcelas já pagas)
            comissoes_result = supabase.table('comissoes_clinica').select('*').execute()
            comissoes_por_clinica = {c['clinica_id']: c for c in (comissoes_result.data or [])}
            
            total_pago_clinicas = 0
            total_comissao_medpix = 0
            
            for venda in result.data:
                clinica_id = venda.get('clinica_id')
                valor_venda = float(venda.get('valor_total', 0) or 0)
                
                # Calcula comissão Indiclin
                comissao_config = comissoes_por_clinica.get(clinica_id, {})
                
                if comissao_config.get('tipo') == 'percentual':
                    percentual = float(comissao_config.get('valor_percentual', 0))
                    comissao_medpix = valor_venda * (percentual / 100)
                else:
                    comissao_medpix = float(comissao_config.get('valor_fixo', 0))
                
                total_comissao_medpix += comissao_medpix
                
                # Valor líquido para clínica
                valor_liquido = valor_venda - comissao_medpix
                valor_parcela = valor_liquido / 2
                
                # Soma apenas parcelas já pagas
                if venda.get('parcela1_clinica_paga', False):
                    total_pago_clinicas += valor_parcela
                
                if venda.get('parcela2_clinica_paga', False):
                    total_pago_clinicas += valor_parcela
            
            # 3. CASHBACK PAGO
            query_cashback = supabase.table('cashback_pagamentos').select('valor, data_pagamento').eq('pago', True)
            
            if data_inicio:
                query_cashback = query_cashback.gte('data_pagamento', f'{data_inicio}T00:00:00')
            if data_fim:
                query_cashback = query_cashback.lte('data_pagamento', f'{data_fim}T23:59:59')
            
            result_cashback = query_cashback.execute()
            total_cashback_pago = sum([float(c.get('valor', 0) or 0) for c in (result_cashback.data or [])])
            
            # 4. LUCRO MedPIX = Faturamento - Pago às Clínicas - Cashback
            lucro_liquido = faturamento_total - total_pago_clinicas - total_cashback_pago
            
            # 5. A PAGAR (parcelas pendentes + cashback pendente)
            total_a_pagar_clinicas = 0
            
            for venda in result.data:
                clinica_id = venda.get('clinica_id')
                valor_venda = float(venda.get('valor_total', 0) or 0)
                
                comissao_config = comissoes_por_clinica.get(clinica_id, {})
                
                if comissao_config.get('tipo') == 'percentual':
                    percentual = float(comissao_config.get('valor_percentual', 0))
                    comissao_medpix = valor_venda * (percentual / 100)
                else:
                    comissao_medpix = float(comissao_config.get('valor_fixo', 0))
                
                valor_liquido = valor_venda - comissao_medpix
                valor_parcela = valor_liquido / 2
                
                # Soma apenas parcelas pendentes
                if not venda.get('parcela1_clinica_paga', False):
                    total_a_pagar_clinicas += valor_parcela
                
                if not venda.get('parcela2_clinica_paga', False):
                    total_a_pagar_clinicas += valor_parcela
            
            # Cashback pendente
            query_cashback_pendente = supabase.table('cashback_pagamentos').select('valor, criado_em').eq('pago', False)
            
            if data_inicio:
                query_cashback_pendente = query_cashback_pendente.gte('criado_em', f'{data_inicio}T00:00:00')
            if data_fim:
                query_cashback_pendente = query_cashback_pendente.lte('criado_em', f'{data_fim}T23:59:59')
            
            result_cashback_pendente = query_cashback_pendente.execute()
            total_cashback_pendente = sum([float(c.get('valor', 0) or 0) for c in (result_cashback_pendente.data or [])])
            
            # ========== RENDERIZA O HTML ==========
            return ui.div(
                {"class": "card-custom", "style": "background: #f8fafc;"},
                ui.h5("📊 Resumo do Período", style="margin-bottom: 1.5rem;"),
                
                # Estatísticas principais
                ui.row(
                    ui.column(4,
                        ui.div(
                            {"style": "text-align: center; padding: 1.5rem; background: white; border-radius: 0.5rem; box-shadow: 0 2px 4px rgba(0,0,0,0.05);"},
                            ui.h3(str(total_vendas), style="margin: 0; color: #1DD1A1; font-weight: bold;"),
                            ui.p("📄 Vendas Realizadas", style="margin: 0.5rem 0 0 0; color: #546E7A; font-size: 0.9rem;")
                        )
                    ),
                    ui.column(4,
                        ui.div(
                            {"style": "text-align: center; padding: 1.5rem; background: white; border-radius: 0.5rem; box-shadow: 0 2px 4px rgba(0,0,0,0.05);"},
                            ui.h3(str(clinicas_unicas), style="margin: 0; color: #06b6d4; font-weight: bold;"),
                            ui.p("🏥 Clínicas Ativas", style="margin: 0.5rem 0 0 0; color: #546E7A; font-size: 0.9rem;")
                        )
                    ),
                    ui.column(4,
                        ui.div(
                            {"style": "text-align: center; padding: 1.5rem; background: white; border-radius: 0.5rem; box-shadow: 0 2px 4px rgba(0,0,0,0.05);"},
                            ui.h3(formatar_moeda(ticket_medio), style="margin: 0; color: #10b981; font-weight: bold; font-size: 1.5rem;"),
                            ui.p("💰 Ticket Médio", style="margin: 0.5rem 0 0 0; color: #546E7A; font-size: 0.9rem;")
                        )
                    )
                ),
                
                ui.hr(),
                
                # Detalhamento Financeiro
                ui.h6("📋 Detalhamento Financeiro", style="margin-top: 1.5rem; margin-bottom: 1rem;"),
                ui.div(
                    {"style": "background: white; border-radius: 0.5rem; padding: 1.5rem;"},
                    ui.row(
                        ui.column(6,
                            ui.h6("💰 RECEITAS", style="color: #10b981; margin-bottom: 1rem;"),
                            ui.div(
                                {"style": "display: grid; gap: 0.5rem;"},
                                ui.div(
                                    {"style": "display: flex; justify-content: space-between; padding: 0.5rem 0; border-bottom: 1px solid #e2e8f0;"},
                                    ui.span("Faturamento Total:", style="color: #546E7A;"),
                                    ui.span(formatar_moeda(faturamento_total), style="font-weight: 600; color: #2D3748;")
                                ),
                                ui.div(
                                    {"style": "display: flex; justify-content: space-between; padding: 0.5rem 0; border-bottom: 1px solid #e2e8f0;"},
                                    ui.span("Comissão MedPIX (12%):", style="color: #546E7A;"),
                                    ui.span(formatar_moeda(total_comissao_medpix), style="font-weight: 600; color: #10b981;")
                                )
                            )
                        ),
                        ui.column(6,
                            ui.h6("💳 DESPESAS", style="color: #ef4444; margin-bottom: 1rem;"),
                            ui.div(
                                {"style": "display: grid; gap: 0.5rem;"},
                                ui.div(
                                    {"style": "display: flex; justify-content: space-between; padding: 0.5rem 0; border-bottom: 1px solid #e2e8f0;"},
                                    ui.span("Pago às Clínicas:", style="color: #546E7A;"),
                                    ui.span(formatar_moeda(total_pago_clinicas), style="font-weight: 600; color: #ef4444;")
                                ),
                                ui.div(
                                    {"style": "display: flex; justify-content: space-between; padding: 0.5rem 0; border-bottom: 1px solid #e2e8f0;"},
                                    ui.span("Cashback Pago:", style="color: #546E7A;"),
                                    ui.span(formatar_moeda(total_cashback_pago), style="font-weight: 600; color: #ef4444;")
                                ),
                                ui.div(
                                    {"style": "display: flex; justify-content: space-between; padding: 0.5rem 0; border-bottom: 2px solid #f59e0b;"},
                                    ui.span("A Pagar (Clínicas + Cashback):", style="color: #546E7A; font-weight: 600;"),
                                    ui.span(formatar_moeda(total_a_pagar_clinicas + total_cashback_pendente), style="font-weight: 600; color: #f59e0b;")
                                )
                            )
                        )
                    ),
                    
                    ui.hr(),
                    
                    ui.div(
                        {"style": "display: flex; justify-content: space-between; padding: 1rem; background: linear-gradient(135deg, #10b981, #059669); border-radius: 0.5rem; margin-top: 1rem;"},
                        ui.h5("💵 LUCRO MedPIX:", style="margin: 0; color: white;"),
                        ui.h4(formatar_moeda(lucro_liquido), style="margin: 0; color: white; font-weight: bold;")
                    )
                )
            )
            
        except Exception as e:
            print(f"Erro contab_resumo_geral: {e}")
            import traceback
            traceback.print_exc()
            return ui.div(ui.p(f"Erro: {str(e)}", style="color: red;"))
            
            
    ###PAGAMENTOS REALIZADOS
    
    @output
    @render.ui
    def contab_pagamentos_realizados():
        """Mostra pagamentos já realizados às clínicas no período"""
        try:
            if not supabase:
                return ui.div()
            
            return ui.div(
                # Apenas Pagamentos às Clínicas
                ui.div(
                    {"class": "card-custom", "style": "background: #dbeafe;"},
                    ui.h5("🏥 Pagamentos Realizados - Clínicas", style="margin-bottom: 1rem; color: #1e40af;"),
                    ui.output_ui("lista_pagamentos_clinicas_realizados")
                )
            )
            
        except Exception as e:
            print(f"Erro contab_pagamentos_realizados: {e}")
            import traceback
            traceback.print_exc()
            return ui.div(ui.p(f"Erro: {str(e)}", style="color: red;"))



    @output
    @render.ui
    def lista_pagamentos_clinicas_realizados():
        """Lista pagamentos de parcelas já efetuados às clínicas"""
        try:
            if not supabase:
                return ui.div()
            
            data_inicio, data_fim = obter_periodo_contabil()
            
            # Busca vendas com pagamento confirmado
            query = supabase.table('vendas').select(
                '*, clinicas(razao_social, nome_fantasia)'
            ).eq('pagamento_confirmado', True)
            
            if data_inicio:
                query = query.gte('criado_em', f'{data_inicio}T00:00:00')
            if data_fim:
                query = query.lte('criado_em', f'{data_fim}T23:59:59')
            
            result = query.order('criado_em', desc=True).execute()
            
            if not result.data:
                return ui.p("Nenhum pagamento realizado no período", style="color: #546E7A; text-align: center; padding: 2rem;")
            
            # Busca comissões de todas as clínicas
            comissoes_result = supabase.table('comissoes_clinica').select('*').execute()
            comissoes_por_clinica = {c['clinica_id']: c for c in (comissoes_result.data or [])}
            
            # Agrupa por clínica
            pagamentos_por_clinica = {}
            
            for venda in result.data:
                clinica_id = venda.get('clinica_id')
                clinica_nome = venda.get('clinicas', {}).get('nome_fantasia') or venda.get('clinicas', {}).get('razao_social', 'N/A')
                
                # Calcula valores
                valor_venda = float(venda.get('valor_total', 0) or 0)
                
                # Calcula comissão Indiclin
                comissao_config = comissoes_por_clinica.get(clinica_id, {})
                
                if comissao_config.get('tipo') == 'percentual':
                    percentual = float(comissao_config.get('valor_percentual', 0))
                    comissao_medpix = valor_venda * (percentual / 100)
                else:
                    comissao_medpix = float(comissao_config.get('valor_fixo', 0))
                
                valor_liquido = valor_venda - comissao_medpix
                valor_parcela = valor_liquido / 2
                
                # Verifica parcelas pagas
                parcela1_paga = venda.get('parcela1_clinica_paga', False)
                parcela2_paga = venda.get('parcela2_clinica_paga', False)
                data_parcela1 = venda.get('data_pagamento_parcela1_clinica')
                data_parcela2 = venda.get('data_pagamento_parcela2_clinica')
                
                # Se não tem parcelas pagas, pula
                if not parcela1_paga and not parcela2_paga:
                    continue
                
                # Agrupa por clínica
                if clinica_id not in pagamentos_por_clinica:
                    pagamentos_por_clinica[clinica_id] = {
                        'nome': clinica_nome,
                        'parcelas_pagas': 0,
                        'total': 0,
                        'detalhes': []
                    }
                
                # Adiciona parcelas pagas
                if parcela1_paga:
                    pagamentos_por_clinica[clinica_id]['parcelas_pagas'] += 1
                    pagamentos_por_clinica[clinica_id]['total'] += valor_parcela
                    pagamentos_por_clinica[clinica_id]['detalhes'].append({
                        'venda': venda.get('numero_venda'),
                        'parcela': 'Parcela 1',
                        'valor': valor_parcela,
                        'data': data_parcela1
                    })
                
                if parcela2_paga:
                    pagamentos_por_clinica[clinica_id]['parcelas_pagas'] += 1
                    pagamentos_por_clinica[clinica_id]['total'] += valor_parcela
                    pagamentos_por_clinica[clinica_id]['detalhes'].append({
                        'venda': venda.get('numero_venda'),
                        'parcela': 'Parcela 2',
                        'valor': valor_parcela,
                        'data': data_parcela2
                    })
            
            if not pagamentos_por_clinica:
                return ui.p("Nenhum pagamento realizado no período", style="color: #546E7A; text-align: center; padding: 2rem;")
            
            # Cria cards
            cards = []
            for clinica_id, dados in pagamentos_por_clinica.items():
                # Detalhes das parcelas
                detalhes_html = []
                for detalhe in dados['detalhes']:
                    data_formatada = pd.to_datetime(detalhe['data']).strftime('%d/%m/%Y') if detalhe['data'] else '-'
                    detalhes_html.append(
                        ui.div(
                            {"style": "background: #f1f5f9; padding: 0.5rem; border-radius: 0.25rem; margin: 0.25rem 0; font-size: 0.85rem;"},
                            ui.p(f"📄 {detalhe['venda']} - {detalhe['parcela']}: {formatar_moeda(detalhe['valor'])}", 
                                 style="margin: 0; color: #475569;"),
                            ui.p(f"📅 {data_formatada}", 
                                 style="margin: 0.25rem 0 0 0; color: #546E7A; font-size: 0.8rem;")
                        )
                    )
                
                card = ui.div(
                    {"style": "background: white; border-radius: 0.5rem; padding: 1rem; margin-bottom: 1rem; border-left: 4px solid #06b6d4;"},
                    ui.h6(f"🏥 {dados['nome']}", style="margin: 0 0 1rem 0;"),
                    ui.p(f"📦 Parcelas pagas: {dados['parcelas_pagas']}", 
                         style="margin: 0.25rem 0; font-size: 0.9rem; color: #546E7A;"),
                    ui.p(f"💰 Total pago: {formatar_moeda(dados['total'])}", 
                         style="margin: 0.25rem 0 1rem 0; font-size: 1.1rem; font-weight: 700; color: #06b6d4;"),
                    ui.hr(style="margin: 0.5rem 0;"),
                    ui.h6("📋 Detalhes:", style="margin: 0.5rem 0; color: #546E7A; font-size: 0.9rem;"),
                    ui.div(*detalhes_html, style="margin-top: 0.5rem;")
                )
                cards.append(card)
            
            # Total geral
            total_geral = sum([d['total'] for d in pagamentos_por_clinica.values()])
            
            cards.append(
                ui.div(
                    {"style": "background: linear-gradient(135deg, #06b6d4, #0891b2); border-radius: 0.5rem; padding: 1rem; margin-top: 1rem;"},
                    ui.row(
                        ui.column(6,
                            ui.h6("💰 TOTAL PAGO ÀS CLÍNICAS:", style="margin: 0; color: white;")
                        ),
                        ui.column(6,
                            ui.div(
                                {"style": "text-align: right;"},
                                ui.h5(formatar_moeda(total_geral), style="margin: 0; color: white; font-weight: bold;")
                            )
                        )
                    )
                )
            )
            
            return ui.div(*cards)
            
        except Exception as e:
            print(f"Erro lista_pagamentos_clinicas_realizados: {e}")
            import traceback
            traceback.print_exc()
            return ui.div(ui.p(f"Erro: {str(e)}", style="color: red;"))
            
    ## PAGAMENTOS PENDENTES

    @output
    @render.ui
    def contab_pagamentos_pendentes():
        try:
            if not supabase:
                return ui.div()
            
            return ui.div(
                # Apenas Clínicas
                ui.div(
                    {"class": "card-custom", "style": "background: #dbeafe;"},
                    ui.h5("🏥 Pagamentos Pendentes - Clínicas", style="margin-bottom: 1rem; color: #1e40af;"),
                    ui.output_ui("lista_pagamentos_pendentes_clinicas")
                )
            )
            
        except Exception as e:
            print(f"Erro contab_pagamentos_pendentes: {e}")
            return ui.div(ui.p(f"Erro: {str(e)}", style="color: red;"))


    @output
    @render.ui
    def lista_pagamentos_pendentes_clinicas():
        """Mostra pagamentos pendentes de parcelas para clínicas"""
        try:
            if not supabase:
                return ui.div()
            
            # Busca vendas com pagamento confirmado
            result = supabase.table('vendas').select(
                '*, clinicas(razao_social, nome_fantasia), itens_venda(*)'
            ).eq('pagamento_confirmado', True).execute()
            
            if not result.data:
                return ui.p("✅ Nenhum pagamento pendente!", style="color: #10b981; text-align: center; padding: 2rem; font-weight: 600;")
            
            # Busca comissões de todas as clínicas
            comissoes_result = supabase.table('comissoes_clinica').select('*').execute()
            comissoes_por_clinica = {c['clinica_id']: c for c in (comissoes_result.data or [])}
            
            # Agrupa por clínica
            pendentes_por_clinica = {}
            
            for venda in result.data:
                clinica_id = venda.get('clinica_id')
                clinica_nome = venda.get('clinicas', {}).get('nome_fantasia') or venda.get('clinicas', {}).get('razao_social', 'N/A')
                
                valor_venda = float(venda.get('valor_total', 0) or 0)
                
                # Calcula comissão
                comissao_config = comissoes_por_clinica.get(clinica_id, {})
                comissao = 0
                
                if comissao_config.get('tipo') == 'percentual':
                    percentual = float(comissao_config.get('valor_percentual', 0))
                    comissao = valor_venda * (percentual / 100)
                else:
                    comissao = float(comissao_config.get('valor_fixo', 0))
                
                valor_liquido = valor_venda - comissao
                valor_parcela = valor_liquido / 2
                
                # Verifica parcelas pendentes
                parcela1_pendente = not venda.get('parcela1_clinica_paga', False)
                
                # Parcela 2: verifica se todos itens foram atendidos
                itens = venda.get('itens_venda', [])
                itens_atendidos = [item for item in itens if item.get('atendido')]
                todos_atendidos = len(itens) > 0 and len(itens_atendidos) == len(itens)
                parcela2_pendente = todos_atendidos and not venda.get('parcela2_clinica_paga', False)
                
                # Se não tem parcelas pendentes, pula
                if not parcela1_pendente and not parcela2_pendente:
                    continue
                
                # Agrupa por clínica
                if clinica_id not in pendentes_por_clinica:
                    pendentes_por_clinica[clinica_id] = {
                        'nome': clinica_nome,
                        'parcelas_pendentes': 0,
                        'total': 0
                    }
                
                # Soma parcelas pendentes
                if parcela1_pendente:
                    pendentes_por_clinica[clinica_id]['parcelas_pendentes'] += 1
                    pendentes_por_clinica[clinica_id]['total'] += valor_parcela
                
                if parcela2_pendente:
                    pendentes_por_clinica[clinica_id]['parcelas_pendentes'] += 1
                    pendentes_por_clinica[clinica_id]['total'] += valor_parcela
            
            if not pendentes_por_clinica:
                return ui.p("✅ Nenhum pagamento pendente!", style="color: #10b981; text-align: center; padding: 2rem; font-weight: 600;")
            
            # Cria cards
            cards = []
            for clinica_id, dados in pendentes_por_clinica.items():
                card = ui.div(
                    {"style": "background: white; border-radius: 0.5rem; padding: 1rem; margin-bottom: 1rem; border-left: 4px solid #06b6d4;"},
                    ui.row(
                        ui.column(8,
                            ui.h6(f"🏥 {dados['nome']}", style="margin: 0 0 0.5rem 0;"),
                            ui.p(f"📦 Parcelas pendentes: {dados['parcelas_pendentes']}", style="margin: 0.25rem 0; font-size: 0.9rem;")
                        ),
                        ui.column(4,
                            ui.div(
                                {"style": "text-align: right;"},
                                ui.h6(formatar_moeda(dados['total']), 
                                     style="margin: 0; color: #06b6d4; font-weight: bold;")
                            )
                        )
                    )
                )
                cards.append(card)
            
            # Total geral
            total_geral = sum([d['total'] for d in pendentes_por_clinica.values()])
            
            cards.append(
                ui.div(
                    {"style": "background: linear-gradient(135deg, #06b6d4, #0891b2); border-radius: 0.5rem; padding: 1rem; margin-top: 1rem;"},
                    ui.row(
                        ui.column(6,
                            ui.h6("💰 TOTAL A PAGAR:", style="margin: 0; color: white;")
                        ),
                        ui.column(6,
                            ui.div(
                                {"style": "text-align: right;"},
                                ui.h5(formatar_moeda(total_geral), style="margin: 0; color: white; font-weight: bold;")
                            )
                        )
                    )
                )
            )
            
            return ui.div(*cards)
            
        except Exception as e:
            print(f"Erro lista_pagamentos_pendentes_clinicas: {e}")
            import traceback
            traceback.print_exc()
            return ui.div(ui.p(f"Erro: {str(e)}", style="color: red;"))         
                    
    @output
    @render.plot
    def contab_grafico_receitas():
        try:
            if not supabase:
                import matplotlib.pyplot as plt
                fig, ax = plt.subplots(figsize=(8, 5))
                ax.text(0.5, 0.5, 'Dados não disponíveis', ha='center', va='center')
                return fig
            
            data_inicio, data_fim = obter_periodo_contabil()
            
            query = supabase.table('vendas').select('criado_em, valor_total').eq('tipo', 'venda').eq('pagamento_confirmado', True)
            
            if data_inicio:
                query = query.gte('criado_em', f'{data_inicio}T00:00:00')
            if data_fim:
                query = query.lte('criado_em', f'{data_fim}T23:59:59')
            
            result = query.execute()
            
            if not result.data:
                import matplotlib.pyplot as plt
                fig, ax = plt.subplots(figsize=(8, 5))
                ax.text(0.5, 0.5, 'Nenhuma venda no período', ha='center', va='center')
                return fig
            
            df = pd.DataFrame(result.data)
            df['criado_em'] = pd.to_datetime(df['criado_em'])
            df['data'] = df['criado_em'].dt.date
            
            # Agrupa por data
            receitas_por_dia = df.groupby('data')['valor_total'].sum().reset_index()
            
            import matplotlib.pyplot as plt
            fig, ax = plt.subplots(figsize=(8, 5))
            ax.bar(receitas_por_dia['data'], receitas_por_dia['valor_total'], 
                   color='#10b981', alpha=0.8, edgecolor='#059669', linewidth=1.5)
            ax.set_xlabel('Data', fontsize=11)
            ax.set_ylabel('Receita (R$)', fontsize=11)
            ax.set_title('Receitas por Dia', fontsize=14, fontweight='bold')
            ax.grid(True, alpha=0.3, axis='y')
            plt.xticks(rotation=45, ha='right')
            plt.tight_layout()
            
            return fig
            
        except Exception as e:
            print(f"Erro contab_grafico_receitas: {e}")
            import matplotlib.pyplot as plt
            fig, ax = plt.subplots(figsize=(8, 5))
            ax.text(0.5, 0.5, 'Erro ao gerar gráfico', ha='center', va='center')
            return fig

    @output
    @render.plot
    def contab_grafico_comissoes():
        try:
            if not supabase:
                import matplotlib.pyplot as plt
                fig, ax = plt.subplots(figsize=(8, 5))
                ax.text(0.5, 0.5, 'Dados não disponíveis', ha='center', va='center')
                return fig
            
            # Busca dados
            faturamento_str = contab_faturamento_total()
            comissoes_vend_str = contab_comissoes_vendedores()
            comissoes_clin_str = contab_comissoes_clinicas()
            lucro_str = contab_lucro_liquido()
            
            # Converte para float
            faturamento = float(faturamento_str.replace('R$', '').replace('.', '').replace(',', '.').strip())
            comissoes_vend = float(comissoes_vend_str.replace('R$', '').replace('.', '').replace(',', '.').strip())
            comissoes_clin = float(comissoes_clin_str.replace('R$', '').replace('.', '').replace(',', '.').strip())
            lucro = float(lucro_str.replace('R$', '').replace('.', '').replace(',', '.').strip())
            
            # Cria gráfico de pizza
            import matplotlib.pyplot as plt
            
            labels = ['Lucro Líquido', 'Com. Vendedores', 'Com. Clínicas']
            sizes = [lucro, comissoes_vend, comissoes_clin]
            colors = ['#10b981', '#f59e0b', '#06b6d4']
            explode = (0.1, 0, 0)  # Destaca o lucro
            
            fig, ax = plt.subplots(figsize=(8, 5))
            ax.pie(sizes, explode=explode, labels=labels, colors=colors,
                   autopct='%1.1f%%', shadow=True, startangle=90)
            ax.axis('equal')
            ax.set_title('Distribuição Financeira', fontsize=14, fontweight='bold')
            plt.tight_layout()
            
            return fig
            
        except Exception as e:
            print(f"Erro contab_grafico_comissoes: {e}")
            import matplotlib.pyplot as plt
            fig, ax = plt.subplots(figsize=(8, 5))
            ax.text(0.5, 0.5, 'Erro ao gerar gráfico', ha='center', va='center')
            return fig 
    
    
    @reactive.Effect
    @reactive.event(input.btn_logout)
    def logout():
        user_data.set(None)
        cliente_logado.set(None) 
        carrinho.set([])
        ui.notification_show("👋 Logout realizado!", type="message")
    

    @output
    @render.ui
    def btn_download_venda_wrapper():
        """Mostra botão de download do PDF da venda"""
        # ========== FORÇA LEITURA DO TRIGGER ==========
        pdf_trigger()  # ← LÊ O TRIGGER
        # ==============================================
        
        print("\n🔍 btn_download_venda_wrapper CHAMADO")
        
        venda_pdf = ultima_venda_pdf()
        print(f"   - ultima_venda_pdf(): {venda_pdf}")
        
        if not venda_pdf:
            print("   ❌ Nenhum PDF disponível\n")
            return ui.div()
        
        print(f"   ✅ PDF disponível!")
        print(f"   - Número: {venda_pdf.get('numero_venda')}")
        print(f"   - Tipo: {venda_pdf.get('tipo')}")
        print(f"   - Tamanho: {len(venda_pdf.get('pdf', b''))} bytes\n")
        
        tipo_texto = "Venda" if venda_pdf['tipo'] == 'venda' else "Orçamento"
        
        return ui.div(
            {"class": "mt-3 p-3", "style": "background: linear-gradient(135deg, #dcfce7, #bbf7d0); border-radius: 0.5rem; border: 2px solid #16a34a; box-shadow: 0 4px 6px rgba(0,0,0,0.1);"},
            ui.row(
                ui.column(8,
                    ui.h5(f"✅ {tipo_texto} Finalizada!", style="color: #16a34a; margin: 0; font-size: 1.2rem;"),
                    ui.p(f"📄 Número: {venda_pdf['numero_venda']}", 
                         style="margin: 0.5rem 0 0 0; font-size: 1rem; color: #15803d; font-weight: 600;")
                ),
                ui.column(4,
                    ui.download_button("btn_download_venda_pdf", "📥 Baixar Imagem",
                                      class_="btn btn-success w-100",
                                      style="font-weight: 600; padding: 0.75rem; font-size: 1rem;")
                )
            )
        )
    
    # Selects dinâmicos
    @output
    @render.ui
    def select_clinica():
        data_changed_trigger()
        try:
            if not supabase:
                return ui.input_select("venda_clinica", "Clínica*", choices={})
            result = supabase.table('clinicas').select('id, nome_fantasia').eq('ativo', True).order('nome_fantasia').execute()
            choices = {str(c['id']): c['nome_fantasia'] for c in result.data} if result.data else {}
            return ui.input_select("venda_clinica", "Clínica*", choices=choices)
        except:
            return ui.input_select("venda_clinica", "Clínica*", choices={})
    
    @output
    @render.ui
    def select_cliente():
        """Select de cliente com informações adicionais"""
        data_changed_trigger()  # Monitora mudanças
        
        try:
            if not supabase:
                return ui.input_select("venda_cliente", "Cliente*", choices={})
            
            user = user_data()
            if not user:
                return ui.input_select("venda_cliente", "Cliente*", choices={})
            
            result = supabase.table('clientes').select(
                'id, nome_completo, cpf, telefone, codigo, foto_url'
            ).eq('vendedor_id', user['id']).eq('ativo', True).order('nome_completo').execute()
            
            if not result.data:
                return ui.div(
                    ui.input_select("venda_cliente", "Cliente*", choices={}),
                    ui.p("Nenhum cliente cadastrado. Cadastre um cliente primeiro!", 
                         style="color: #f59e0b; font-size: 0.85rem; margin-top: 0.5rem;")
                )
            
            # Monta choices com nome e código
            choices = {}
            for c in result.data:
                nome = c['nome_completo']
                codigo = c.get('codigo', '')
                choices[str(c['id'])] = f"{nome} ({codigo})"
            
            return ui.div(
                ui.input_select("venda_cliente", "Cliente*", choices=choices),
                ui.output_ui("info_cliente_selecionado")  # ← Mostra detalhes
            )
            
        except Exception as e:
            print(f"Erro select_cliente: {e}")
            return ui.input_select("venda_cliente", "Cliente*", choices={})

    @output
    @render.ui
    def info_cliente_selecionado():
        """Exibe CPF, telefone e foto do cliente selecionado"""
        try:
            cliente_id = input.venda_cliente()
            if not cliente_id or not supabase:
                return ui.div()
            
            # Busca dados completos do cliente
            result = supabase.table('clientes').select('*').eq('id', cliente_id).execute()
            
            if not result.data:
                return ui.div()
            
            cliente = result.data[0]
            
            cpf = formatar_cpf(cliente.get('cpf', ''))
            telefone = formatar_whatsapp(cliente.get('telefone', '')) or '-'
            email = cliente.get('email', '-')
            foto_url = cliente.get('foto_url', '')
            
            # HTML da foto
            foto_html = ''
            if foto_url:
                foto_html = f'''
                    <img src="{foto_url}" 
                         style="width: 80px; height: 80px; border-radius: 50%; 
                                object-fit: cover; border: 3px solid #1DD1A1; 
                                box-shadow: 0 2px 4px rgba(0,0,0,0.1);"
                         onerror="this.style.display='none'">
                '''
            else:
                foto_html = '''
                    <div style="width: 80px; height: 80px; border-radius: 50%; 
                                background: linear-gradient(135deg, #1DD1A1, #0D9488); 
                                display: flex; align-items: center; justify-content: center; 
                                color: white; font-size: 2rem; font-weight: bold;">
                        👤
                    </div>
                '''
            
            return ui.div(
                {"class": "mt-3 p-3", 
                 "style": "background: linear-gradient(135deg, #f0f9ff, #e0f2fe); border-radius: 0.5rem; border: 2px solid #0ea5e9;"},
                ui.row(
                    ui.column(3,
                        ui.HTML(f'<div style="text-align: center;">{foto_html}</div>')
                    ),
                    ui.column(9,
                        ui.h6("✅ Cliente Selecionado", 
                              style="margin: 0 0 0.75rem 0; color: #0c4a6e; font-weight: 600;"),
                        ui.div(
                            {"style": "display: grid; grid-template-columns: 1fr 1fr; gap: 0.5rem;"},
                            ui.p(f"📄 CPF: {cpf}", 
                                 style="margin: 0; font-size: 0.9rem; color: #0369a1;"),
                            ui.p(f"📱 Tel: {telefone}", 
                                 style="margin: 0; font-size: 0.9rem; color: #0369a1;"),
                            ui.p(f"📧 Email: {email}", 
                                 style="margin: 0; font-size: 0.9rem; color: #0369a1; grid-column: 1 / -1;")
                        )
                    )
                )
            )
            
        except Exception as e:
            print(f"Erro info_cliente_selecionado: {e}")
            return ui.div()
    
    @output
    @render.ui
    def select_procedimento():
        try:
            if not supabase or not input.venda_clinica():
                return ui.input_select("venda_proc", "Procedimento*", choices={})
            result = supabase.table('procedimentos').select('id, nome, preco').eq('clinica_id', input.venda_clinica()).eq('ativo', True).execute()
            choices = {str(p['id']): f"{p['nome']} - {formatar_moeda(p['preco'])}" for p in result.data} if result.data else {}
            return ui.input_select("venda_proc", "Procedimento*", choices=choices)
        except:
            return ui.input_select("venda_proc", "Procedimento*", choices={})
    
    @output
    @render.ui
    def select_grupo():
        try:
            if not supabase:
                return ui.input_select("proc_grupo", "Grupo*", choices={})
            result = supabase.table('grupos_procedimentos').select('id, nome').execute()
            choices = {str(g['id']): g['nome'] for g in result.data} if result.data else {}
            return ui.input_select("proc_grupo", "Grupo*", choices=choices)
        except:
            return ui.input_select("proc_grupo", "Grupo*", choices={})
    
    # ========== ESTATÍSTICAS DO DASHBOARD PRINCIPAL ==========
    @output
    @render.text
    def stat_vendas():
        try:
            if not supabase: 
                return "0"
            result = supabase.table('vendas').select('id', count='exact').eq('tipo', 'venda').execute()
            count = result.count if hasattr(result, 'count') and result.count is not None else 0
            return safe_str(count)
        except Exception as e:
            print(f"Erro stat_vendas: {e}")
            return "0"

    @output
    @render.text
    def stat_faturamento():
        try:
            if not supabase: 
                return "R$ 0,00"
            result = supabase.table('vendas').select('valor_total').eq('tipo', 'venda').execute()
            if not result.data:
                return "R$ 0,00"
            total = sum([float(v.get('valor_total', 0) or 0) for v in result.data])
            return formatar_moeda(total)
        except Exception as e:
            print(f"Erro stat_faturamento: {e}")
            return "R$ 0,00"

    @output
    @render.text
    def stat_clientes():
        try:
            if not supabase: 
                return "0"
            result = supabase.table('clientes').select('id', count='exact').execute()
            count = result.count if hasattr(result, 'count') and result.count is not None else 0
            return safe_str(count)
        except Exception as e:
            print(f"Erro stat_clientes: {e}")
            return "0"

    # ========== MODAL DE EDIÇÃO DE USUÁRIO ==========
    @reactive.Effect
    def _monitor_editar_usuario():
        """Abre modal para editar usuário"""
        try:
            usuario_id = None
            try:
                usuario_id = input.editar_usuario_id()
            except:
                return
            
            if not usuario_id or not supabase:
                return
            
            # Busca dados do usuário
            result = supabase.table('usuarios').select('*').eq('id', usuario_id).execute()
            
            if not result.data:
                ui.notification_show("❌ Usuário não encontrado!", type="error")
                return
            
            usuario = result.data[0]
            
            # Remove modal anterior se existir
            ui.remove_ui(selector=f"#edit_modal_{usuario_id}")
            
            # Cria modal de edição CORRIGIDO
            modal_html = f'''
            <div id="edit_modal_{usuario_id}" style="
                position: fixed; top: 0; left: 0; width: 100%; height: 100%; 
                background: rgba(0,0,0,0.8); z-index: 9999; 
                display: flex; align-items: center; justify-content: center;
                overflow-y: auto; padding: 2rem;
            ">
                <div style="
                    background: white; border-radius: 1rem; padding: 2rem; 
                    max-width: 600px; width: 100%;
                " onclick="event.stopPropagation()">
                    <h3 style="color: #1DD1A1; margin-bottom: 1.5rem;">✏️ Editar Usuário</h3>
                    
                    <form id="form_edit_usuario_{usuario_id}">
                        <div style="margin-bottom: 1rem;">
                            <label style="display: block; font-weight: 600; margin-bottom: 0.5rem;">Nome</label>
                            <input type="text" id="edit_nome_{usuario_id}" value="{usuario.get('nome', '')}" 
                                   style="width: 100%; padding: 0.75rem; border: 2px solid #e2e8f0; border-radius: 0.5rem;">
                        </div>
                        
                        <div style="margin-bottom: 1rem;">
                            <label style="display: block; font-weight: 600; margin-bottom: 0.5rem;">Email</label>
                            <input type="email" id="edit_email_{usuario_id}" value="{usuario.get('email', '')}" 
                                   style="width: 100%; padding: 0.75rem; border: 2px solid #e2e8f0; border-radius: 0.5rem;">
                        </div>
                        
                        <div style="margin-bottom: 1rem;">
                            <label style="display: block; font-weight: 600; margin-bottom: 0.5rem;">Telefone</label>
                            <input type="text" id="edit_telefone_{usuario_id}" value="{usuario.get('telefone', '')}" 
                                   style="width: 100%; padding: 0.75rem; border: 2px solid #e2e8f0; border-radius: 0.5rem;">
                        </div>
                        
                        {f'''<div style="margin-bottom: 1rem;">
                            <label style="display: block; font-weight: 600; margin-bottom: 0.5rem;">💳 Chave PIX</label>
                            <input type="text" id="edit_pix_{usuario_id}" value="{usuario.get('pix_chave', '')}" 
                                   style="width: 100%; padding: 0.75rem; border: 2px solid #e2e8f0; border-radius: 0.5rem;">
                        </div>''' if usuario.get('tipo_usuario') == 'vendedor' else ''}
                        
                        {f'''<div style="margin-bottom: 1rem;">
                            <label style="display: block; font-weight: 600; margin-bottom: 0.5rem;">Comissão (%)</label>
                            <input type="number" id="edit_comissao_perc_{usuario_id}" value="{usuario.get('comissao_percentual', 0)}" 
                                   min="0" max="100" step="0.01" 
                                   style="width: 100%; padding: 0.75rem; border: 2px solid #e2e8f0; border-radius: 0.5rem;">
                        </div>''' if usuario.get('tipo_usuario') == 'vendedor' else ''}
                        
                        <div style="display: flex; gap: 1rem; margin-top: 2rem;">
                            <button type="button" onclick="
                                const nome = document.getElementById('edit_nome_{usuario_id}').value;
                                const email = document.getElementById('edit_email_{usuario_id}').value;
                                const telefone = document.getElementById('edit_telefone_{usuario_id}').value;
                                const pix = document.getElementById('edit_pix_{usuario_id}')?.value || '';
                                const comissao = document.getElementById('edit_comissao_perc_{usuario_id}')?.value || 0;
                                
                                const data = {{
                                    id: '{usuario_id}',
                                    nome: nome,
                                    email: email,
                                    telefone: telefone,
                                    pix_chave: pix,
                                    comissao_percentual: parseFloat(comissao)
                                }};
                                
                                Shiny.setInputValue('salvar_edicao_usuario', JSON.stringify(data), {{priority: 'event'}});
                                document.getElementById('edit_modal_{usuario_id}').remove();
                            " style="
                                flex: 1; background: #10b981; color: white; border: none; 
                                padding: 0.75rem; border-radius: 0.5rem; font-weight: 600; cursor: pointer;
                            ">💾 Salvar</button>
                            
                            <button type="button" onclick="document.getElementById('edit_modal_{usuario_id}').remove()" 
                                style="
                                    flex: 1; background: #ef4444; color: white; border: none; 
                                    padding: 0.75rem; border-radius: 0.5rem; font-weight: 600; cursor: pointer;
                                ">❌ Cancelar</button>
                        </div>
                    </form>
                </div>
            </div>
            '''
            
            ui.insert_ui(
                selector="body",
                where="beforeEnd",
                ui=ui.HTML(modal_html)
            )
            
        except Exception as e:
            print(f"Erro _monitor_editar_usuario: {e}")
            import traceback
            traceback.print_exc()
            ui.notification_show(f"❌ Erro: {str(e)}", type="error")

    # ========== SALVAR EDIÇÃO DE USUÁRIO ==========
    @reactive.Effect
    def _monitor_salvar_edicao_usuario():
        """Salva edições do usuário"""
        try:
            dados_json = None
            try:
                dados_json = input.salvar_edicao_usuario()
            except:
                return
            
            if not dados_json or not supabase:
                return
            
            import json
            dados = json.loads(dados_json)
            
            usuario_id = dados.get('id')
            
            # Prepara update
            update_data = {
                'nome': dados.get('nome'),
                'email': dados.get('email'),
                'telefone': dados.get('telefone')
            }
            
            if dados.get('pix_chave'):
                update_data['pix_chave'] = dados['pix_chave']
            
            if dados.get('comissao_percentual') is not None:
                update_data['comissao_percentual'] = dados['comissao_percentual']
            
            # Atualiza no banco
            supabase.table('usuarios').update(update_data).eq('id', usuario_id).execute()
            
            ui.notification_show(
                f"✅ Usuário atualizado com sucesso!\n"
                f"👤 {dados['nome']}",
                type="message",
                duration=5
            )
            
        except Exception as e:
            print(f"Erro _monitor_salvar_edicao_usuario: {e}")
            import traceback
            traceback.print_exc()
            ui.notification_show(f"❌ Erro ao salvar: {str(e)}", type="error")


    # ========== VER DETALHES DA VENDA ==========
    @reactive.Effect
    def _monitor_ver_detalhes_venda():
        """Mostra modal com detalhes completos da venda"""
        try:
            venda_id = None
            try:
                venda_id = input.ver_detalhes_venda_id()
            except:
                return
            
            if not venda_id or not supabase:
                return
            
            # Busca venda completa com itens
            result = supabase.table('vendas').select(
                '*, clientes(*), clinicas(*), usuarios!vendas_vendedor_id_fkey(nome), itens_venda(*)'
            ).eq('id', venda_id).execute()
            
            if not result.data:
                ui.notification_show("❌ Venda não encontrada!", type="error")
                return
            
            venda = result.data[0]
            cliente = venda.get('clientes', {})
            clinica = venda.get('clinicas', {})
            vendedor = venda.get('usuarios')  # Pode ser None
            vendedor_nome = vendedor.get('nome', 'N/A') if vendedor else 'Sem vendedor'
            itens = venda.get('itens_venda', [])
            
            # Monta tabela de itens
            itens_html = ""
            for item in itens:
                itens_html += f'''
                <tr>
                    <td style="padding: 0.5rem; border-bottom: 1px solid #e2e8f0;">{item.get('nome_procedimento')}</td>
                    <td style="padding: 0.5rem; border-bottom: 1px solid #e2e8f0; text-align: center;">{item.get('quantidade')}</td>
                    <td style="padding: 0.5rem; border-bottom: 1px solid #e2e8f0; text-align: right;">{formatar_moeda(item.get('preco_unitario'))}</td>
                    <td style="padding: 0.5rem; border-bottom: 1px solid #e2e8f0; text-align: right; font-weight: 600;">{formatar_moeda(item.get('preco_total'))}</td>
                </tr>
                '''
            
            modal_html = f'''
            <div id="details_modal_{venda_id}" style="
                position: fixed; top: 0; left: 0; width: 100%; height: 100%; 
                background: rgba(0,0,0,0.8); z-index: 9999; 
                display: flex; align-items: center; justify-content: center;
                overflow-y: auto; padding: 2rem;
            " onclick="this.style.display='none'">
                <div style="
                    background: white; border-radius: 1rem; padding: 2rem; 
                    max-width: 800px; width: 100%;
                " onclick="event.stopPropagation()">
                    <h3 style="color: #1DD1A1; margin-bottom: 1.5rem;">📄 Detalhes da Venda</h3>
                    
                    <div style="background: #f8fafc; padding: 1rem; border-radius: 0.5rem; margin-bottom: 1rem;">
                        <h5 style="margin: 0 0 0.5rem 0; color: #1DD1A1;">Informações Gerais</h5>
                        <p style="margin: 0.25rem 0;"><strong>Número:</strong> {venda['numero_venda']}</p>
                        <p style="margin: 0.25rem 0;"><strong>Tipo:</strong> {venda['tipo'].title()}</p>
                        <p style="margin: 0.25rem 0;"><strong>Status:</strong> {venda.get('status', 'N/A')}</p>
                        <p style="margin: 0.25rem 0;"><strong>Data:</strong> {pd.to_datetime(venda['criado_em']).strftime('%d/%m/%Y %H:%M')}</p>
                    </div>
                    
                    <div style="background: #f0f9ff; padding: 1rem; border-radius: 0.5rem; margin-bottom: 1rem;">
                        <h5 style="margin: 0 0 0.5rem 0; color: #0369a1;">👤 Cliente</h5>
                        <p style="margin: 0.25rem 0;"><strong>Nome:</strong> {cliente.get('nome_completo', 'N/A')}</p>
                        <p style="margin: 0.25rem 0;"><strong>CPF:</strong> {formatar_cpf(cliente.get('cpf', ''))}</p>
                        <p style="margin: 0.25rem 0;"><strong>Telefone:</strong> {cliente.get('telefone', '-')}</p>
                    </div>
                    
                    <div style="background: #ecfdf5; padding: 1rem; border-radius: 0.5rem; margin-bottom: 1rem;">
                        <h5 style="margin: 0 0 0.5rem 0; color: #059669;">🏥 Clínica</h5>
                        <p style="margin: 0.25rem 0;"><strong>Razão Social:</strong> {clinica.get('razao_social', 'N/A')}</p>
                        <p style="margin: 0.25rem 0;"><strong>CNPJ:</strong> {formatar_cnpj(clinica.get('cnpj', ''))}</p>
                        <p style="margin: 0.25rem 0;"><strong>WhatsApp:</strong> {formatar_whatsapp(clinica.get('whatsapp', '-'))}</p>
                    </div>
                    
                    <div style="background: #fef3c7; padding: 1rem; border-radius: 0.5rem; margin-bottom: 1rem;">
                        <h5 style="margin: 0 0 0.5rem 0; color: #92400e;">💼 Vendedor</h5>
                        <p style="margin: 0.25rem 0;"><strong>Nome:</strong> {vendedor_nome}</p>
                    </div>
                    
                    <div style="margin: 1.5rem 0;">
                        <h5 style="margin-bottom: 1rem; color: #1DD1A1;">📋 Procedimentos</h5>
                        <table style="width: 100%; border-collapse: collapse;">
                            <thead>
                                <tr style="background: #f1f5f9;">
                                    <th style="padding: 0.75rem; text-align: left; border-bottom: 2px solid #cbd5e1;">Procedimento</th>
                                    <th style="padding: 0.75rem; text-align: center; border-bottom: 2px solid #cbd5e1;">Qtd</th>
                                    <th style="padding: 0.75rem; text-align: right; border-bottom: 2px solid #cbd5e1;">Preço Unit.</th>
                                    <th style="padding: 0.75rem; text-align: right; border-bottom: 2px solid #cbd5e1;">Total</th>
                                </tr>
                            </thead>
                            <tbody>
                                {itens_html}
                            </tbody>
                        </table>
                    </div>
                    
                    <div style="background: linear-gradient(135deg, #10b981, #059669); color: white; padding: 1rem; border-radius: 0.5rem; display: flex; justify-content: space-between; align-items: center; margin-top: 1rem;">
                        <span style="font-weight: 600; font-size: 1.1rem;">TOTAL:</span>
                        <span style="font-weight: 700; font-size: 1.5rem;">{formatar_moeda(venda['valor_total'])}</span>
                    </div>
                    
                    <button onclick="document.getElementById('details_modal_{venda_id}').style.display='none'" 
                        style="
                            width: 100%; background: #1DD1A1; color: white; border: none; 
                            padding: 0.75rem; border-radius: 0.5rem; font-weight: 600; 
                            cursor: pointer; margin-top: 1rem;
                        ">❌ Fechar</button>
                </div>
            </div>
            '''
            
            ui.insert_ui(
                selector="body",
                where="beforeEnd",
                ui=ui.HTML(modal_html)
            )
            
        except Exception as e:
            print(f"Erro _monitor_ver_detalhes_venda: {e}")
            import traceback
            traceback.print_exc()
            ui.notification_show(f"❌ Erro: {str(e)}", type="error")


 
    @reactive.Effect
    def _monitor_cancelar_venda():
        """Cancela uma venda"""
        try:
            venda_id = None
            try:
                venda_id = input.cancelar_venda_id()
            except:
                return
            
            if not venda_id or not supabase:
                return
            
            # Busca venda
            result = supabase.table('vendas').select('numero_venda, status').eq('id', venda_id).execute()
            
            if not result.data:
                ui.notification_show("❌ Venda não encontrada!", type="error")
                return
            
            venda = result.data[0]
            
            if venda['status'] == 'cancelado':
                ui.notification_show("⚠️ Esta venda já está cancelada!", type="warning")
                return
            
            # Atualiza status
            supabase.table('vendas').update({
                'status': 'cancelado',
                'cancelado_em': datetime.now().isoformat()
            }).eq('id', venda_id).execute()
            
            ui.notification_show(
                f"✅ Venda cancelada com sucesso!\n📄 {venda['numero_venda']}",
                type="message",
                duration=5
            )
            
        except Exception as e:
            print(f"Erro _monitor_cancelar_venda: {e}")
            import traceback
            traceback.print_exc()
            ui.notification_show(f"❌ Erro: {str(e)}", type="error")


    @output
    @render.ui
    def lista_pagamentos_clinicas():
        try:
            if not supabase:
                return ui.div()
            
            clinicas_result = supabase.table('clinicas').select('*').eq('ativo', True).execute()
            
            if not clinicas_result.data:
                return ui.div(
                    {"style": "text-align: center; padding: 3rem; color: #94a3b8;"},
                    ui.h5("🔭 Nenhuma clínica cadastrada")
                )
            
            filtro = input.filtro_pagamento_clinicas()
            busca = input.buscar_pagamento_clinica()
            
            cards = []
            
            for clinica in clinicas_result.data:
                nome_clinica = clinica.get('nome_fantasia') or clinica.get('razao_social', 'N/A')
                
                if busca and busca.lower() not in nome_clinica.lower():
                    continue
                
                clinica_id = clinica['id']
                
                # Busca PIX
                pix_chave = None
                pix_tipo = None
                try:
                    dados_pix = json.loads(clinica.get('dados_pix', '{}'))
                    pix_chave = dados_pix.get('chave')
                    pix_tipo = dados_pix.get('tipo', 'Não informado')
                except:
                    pass
                
                # Busca comissão
                comissao_result = supabase.table('comissoes_clinica').select('*').eq('clinica_id', clinica_id).execute()
                comissao_config = comissao_result.data[0] if comissao_result.data else {}
                
                # DEBUG: Mostra comissão encontrada
                print(f"\n{'='*60}")
                print(f"🔍 DEBUG COMISSÃO - {nome_clinica}")
                print(f"Clinica ID: {clinica_id}")
                print(f"Comissão encontrada: {comissao_result.data}")
                print(f"Tipo: {comissao_config.get('tipo')}")
                print(f"Percentual: {comissao_config.get('valor_percentual')} (tipo: {type(comissao_config.get('valor_percentual'))})")
                print(f"{'='*60}\n")
                
                # Busca vendas da clínica
                vendas_result = supabase.table('vendas').select(
                    '*, itens_venda(*)'
                ).eq('clinica_id', clinica_id).eq('pagamento_confirmado', True).execute()
                
                if not vendas_result.data:
                    continue
                
                # Calcula totais DETALHADOS
                total_parcela1_pendente = 0
                total_parcela2_pendente = 0
                total_parcela1_paga = 0
                total_parcela2_paga = 0
                parcelas1_pendentes = []
                parcelas2_pendentes = []
                vendas_pagas_completo = 0
                total_vendas = len(vendas_result.data)
                
                for venda in vendas_result.data:
                    # Calcula valor base
                    valor_base = float(venda.get('valor_total', 0) or 0)
                    
                    # Calcula comissão
                    if comissao_config.get('tipo') == 'percentual':
                        comissao = valor_base * (comissao_config.get('valor_percentual', 0) / 100)
                    else:
                        comissao = comissao_config.get('valor_fixo', 0)
                    
                    valor_liquido = valor_base - comissao
                    valor_parcela = valor_liquido / 2
                    
                    # Parcela 1
                    if venda.get('parcela1_clinica_paga', False):
                        total_parcela1_paga += valor_parcela
                    else:
                        total_parcela1_pendente += valor_parcela
                        parcelas1_pendentes.append({
                            'venda_id': venda['id'],
                            'numero': venda['numero_venda'],
                            'valor': valor_parcela,
                            'data_confirmacao': venda.get('data_pagamento_confirmado')
                        })
                    
                    # Parcela 2 (só se todos itens atendidos)
                    itens = venda.get('itens_venda', [])
                    itens_atendidos = [item for item in itens if item.get('atendido')]
                    todos_atendidos = len(itens) > 0 and len(itens_atendidos) == len(itens)                    
                    if venda.get('parcela2_clinica_paga', False):
                        total_parcela2_paga += valor_parcela
                    elif todos_atendidos:
                        total_parcela2_pendente += valor_parcela
                        parcelas2_pendentes.append({
                            'venda_id': venda['id'],
                            'numero': venda['numero_venda'],
                            'valor': valor_parcela,
                            'atendimentos': f"{len(itens_atendidos)}/{len(itens)}"
                        })
                    
                    # Conta vendas totalmente pagas
                    if venda.get('parcela1_clinica_paga') and venda.get('parcela2_clinica_paga'):
                        vendas_pagas_completo += 1
                
                total_pendente = total_parcela1_pendente + total_parcela2_pendente
                total_pago = total_parcela1_paga + total_parcela2_paga
                
                # Aplica filtros
                if filtro == "pendentes" and total_pendente == 0:
                    continue
                elif filtro == "pagos" and vendas_pagas_completo == 0:
                    continue
                
                cor_border = "#10b981" if total_pendente == 0 else "#f59e0b"
                
                card = ui.div(
                    {"class": "card-custom", "style": f"margin-bottom: 1.5rem; border-left: 4px solid {cor_border};"},
                    ui.row(
                        ui.column(7,
                            # HEADER
                            ui.div(
                                {"style": "background: linear-gradient(135deg, #1DD1A1, #0D9488); padding: 1rem; border-radius: 0.5rem; margin-bottom: 1rem; color: white;"},
                                ui.h5(nome_clinica, style="margin: 0 0 0.5rem 0;"),
                                ui.p(f"🏥 CNPJ: {formatar_cnpj(clinica.get('cnpj', ''))}", style="margin: 0; font-size: 0.85rem; opacity: 0.9;")
                            ),
                            
                            # RESUMO GERAL
                            ui.div(
                                {"style": "background: #f8fafc; padding: 1rem; border-radius: 0.5rem; margin-bottom: 1rem;"},
                                ui.h6("📊 Resumo Geral", style="margin: 0 0 0.75rem 0; color: #2D3748;"),
                                ui.row(
                                    ui.column(6,
                                        ui.p(f"📄 Total de vendas: {total_vendas}", style="margin: 0.25rem 0; font-size: 0.9rem;"),
                                        ui.p(f"✅ Vendas quitadas: {vendas_pagas_completo}", style="margin: 0.25rem 0; font-size: 0.9rem; color: #10b981; font-weight: 600;"),
                                        ui.p(f"⏳ Vendas pendentes: {total_vendas - vendas_pagas_completo}", style="margin: 0.25rem 0; font-size: 0.9rem; color: #f59e0b; font-weight: 600;")
                                    ),
                                    ui.column(6,
                                        ui.p(f"💰 Total pago: {formatar_moeda(total_pago)}", style="margin: 0.25rem 0; font-size: 0.9rem; color: #10b981; font-weight: 600;"),
                                        ui.p(f"⏳ Total pendente: {formatar_moeda(total_pendente)}", style="margin: 0.25rem 0; font-size: 0.9rem; color: #f59e0b; font-weight: 600;")
                                    )
                                )
                            ),
                            
                            # PARCELA 1
                            ui.div(
                                {"style": "background: #fef3c7; padding: 1rem; border-radius: 0.5rem; margin-bottom: 0.75rem; border: 2px solid #f59e0b;"},
                                ui.h6("💰 Parcela 1 (50% - Paga na Confirmação)", style="margin: 0 0 0.5rem 0; color: #92400e;"),
                                ui.row(
                                    ui.column(6,
                                        ui.p(f"✅ Pago: {formatar_moeda(total_parcela1_paga)}", 
                                             style="margin: 0.25rem 0; font-size: 0.85rem; color: #10b981; font-weight: 600;"),
                                        ui.p(f"⏳ Pendente: {formatar_moeda(total_parcela1_pendente)}", 
                                             style="margin: 0.25rem 0; font-size: 0.85rem; color: #f59e0b; font-weight: 600;")
                                    ),
                                    ui.column(6,
                                        ui.p(f"📦 Vendas a pagar: {len(parcelas1_pendentes)}", 
                                             style="margin: 0.25rem 0; font-size: 0.85rem;")
                                    )
                                ),
                                ui.div(
                                    {"style": "margin-top: 0.5rem; padding-top: 0.5rem; border-top: 1px solid #f59e0b;"},
                                    *[
                                        ui.p(f"• {p['numero']}: {formatar_moeda(p['valor'])}", 
                                             style="margin: 0.15rem 0; font-size: 0.75rem; color: #78350f;")
                                        for p in parcelas1_pendentes[:3]
                                    ],
                                    ui.p(f"... e mais {len(parcelas1_pendentes) - 3} vendas", 
                                         style="margin: 0.15rem 0; font-size: 0.75rem; font-style: italic; color: #78350f;") if len(parcelas1_pendentes) > 3 else None
                                ) if parcelas1_pendentes else None
                            ) if (total_parcela1_pendente > 0 or total_parcela1_paga > 0) else None,
                            
                            # PARCELA 2
                            ui.div(
                                {"style": "background: #dbeafe; padding: 1rem; border-radius: 0.5rem; margin-bottom: 0.75rem; border: 2px solid #3b82f6;"},
                                ui.h6("💰 Parcela 2 (50% - Paga após Atendimentos)", style="margin: 0 0 0.5rem 0; color: #1e40af;"),
                                ui.row(
                                    ui.column(6,
                                        ui.p(f"✅ Pago: {formatar_moeda(total_parcela2_paga)}", 
                                             style="margin: 0.25rem 0; font-size: 0.85rem; color: #10b981; font-weight: 600;"),
                                        ui.p(f"⏳ Pendente: {formatar_moeda(total_parcela2_pendente)}", 
                                             style="margin: 0.25rem 0; font-size: 0.85rem; color: #3b82f6; font-weight: 600;")
                                    ),
                                    ui.column(6,
                                        ui.p(f"📦 Vendas prontas: {len(parcelas2_pendentes)}", 
                                             style="margin: 0.25rem 0; font-size: 0.85rem;")
                                    )
                                ),
                                ui.div(
                                    {"style": "margin-top: 0.5rem; padding-top: 0.5rem; border-top: 1px solid #3b82f6;"},
                                    *[
                                        ui.p(f"• {p['numero']}: {formatar_moeda(p['valor'])} (Atend: {p['atendimentos']})", 
                                             style="margin: 0.15rem 0; font-size: 0.75rem; color: #1e40af;")
                                        for p in parcelas2_pendentes[:3]
                                    ],
                                    ui.p(f"... e mais {len(parcelas2_pendentes) - 3} vendas", 
                                         style="margin: 0.15rem 0; font-size: 0.75rem; font-style: italic; color: #1e40af;") if len(parcelas2_pendentes) > 3 else None
                                ) if parcelas2_pendentes else None
                            ) if (total_parcela2_pendente > 0 or total_parcela2_paga > 0) else None,
                            
                            # PIX INFO
                            ui.div(
                                {"style": "background: #dcfce7; padding: 0.75rem; border-radius: 0.5rem; border: 2px solid #10b981;"},
                                ui.h6("💳 Dados PIX", style="margin: 0 0 0.5rem 0; color: #15803d;"),
                                ui.p(f"Chave: {pix_chave or '❌ Não cadastrada'}", 
                                     style="margin: 0.25rem 0; font-size: 0.85rem; font-weight: 600; font-family: monospace;"),
                                ui.p(f"Tipo: {pix_tipo}", 
                                     style="margin: 0.25rem 0; font-size: 0.75rem; color: #15803d;") if pix_chave else None
                            )
                        ),
                        ui.column(5,
                            ui.div(
                                {"style": "text-align: center; padding: 1rem;"},
                                
                                # STATUS GERAL
                                ui.div(
                                    {"style": f"background: {cor_border}; color: white; padding: 1rem; border-radius: 0.5rem; margin-bottom: 1rem;"},
                                    ui.h4("💵 TOTAL PENDENTE", style="margin: 0 0 0.5rem 0; font-size: 1rem;"),
                                    ui.h3(formatar_moeda(total_pendente), style="margin: 0; font-size: 1.8rem; font-weight: bold;")
                                ),
                                
                                # Botão Gerar PIX
                                ui.tags.button(
                                    "📲 Gerar QR Code PIX",
                                    class_="btn btn-info w-100 mb-2",
                                    onclick=f"Shiny.setInputValue('gerar_pix_clinica_id', '{clinica_id}', {{priority: 'event'}})",
                                    style="font-weight: 600; padding: 0.75rem; font-size: 0.9rem;"
                                ) if total_pendente > 0 and pix_chave else None,
                                
                                # Botão Pagar Parcela 1
                                ui.tags.button(
                                    f"💸 Pagar Parcela 1\n{len(parcelas1_pendentes)} venda(s) - {formatar_moeda(total_parcela1_pendente)}",
                                    class_="btn btn-warning w-100 mb-2",
                                    onclick=f"Shiny.setInputValue('confirmar_pagar_parcela1', '{clinica_id}', {{priority: 'event'}})",
                                    style="font-weight: 600; padding: 0.75rem; white-space: pre-line; font-size: 0.85rem;"
                                ) if len(parcelas1_pendentes) > 0 else None,
                                
                                # Botão Pagar Parcela 2
                                ui.tags.button(
                                    f"💸 Pagar Parcela 2\n{len(parcelas2_pendentes)} venda(s) - {formatar_moeda(total_parcela2_pendente)}",
                                    class_="btn btn-primary w-100 mb-2",
                                    onclick=f"Shiny.setInputValue('confirmar_pagar_parcela2', '{clinica_id}', {{priority: 'event'}})",
                                    style="font-weight: 600; padding: 0.75rem; white-space: pre-line; font-size: 0.85rem;"
                                ) if len(parcelas2_pendentes) > 0 else None,
                                
                                # Status
                                ui.div(
                                    {"class": "btn btn-success w-100", "style": "font-weight: 600; padding: 1rem; font-size: 1.1rem;"},
                                    "✅ Tudo Pago!"
                                ) if total_pendente == 0 else None
                            )
                        )
                    )
                )
                cards.append(card)
            
            if not cards:
                return ui.div(
                    {"style": "text-align: center; padding: 3rem; color: #94a3b8;"},
                    ui.h5("🔭 Nenhuma clínica encontrada com os filtros aplicados")
                )
            
            return ui.div(*cards)
            
        except Exception as e:
            print(f"Erro lista_pagamentos_clinicas: {e}")
            import traceback
            traceback.print_exc()
            return ui.div(ui.p(f"Erro: {str(e)}", style="color: red;"))
        
    # ========== EFFECT: PAGAR PARCELA 1 ==========
    @reactive.Effect
    def _monitor_pagar_parcela1():
        try:
            clinica_id = None
            try:
                clinica_id = input.pagar_parcela1_clinica()
            except:
                return
            
            if not clinica_id or not supabase:
                return
            
            print(f"\n{'='*60}")
            print(f"💸 PAGAR PARCELA 1 - DEBUG")
            print(f"{'='*60}")
            
            user = user_data()
            if not user:
                return
            
            # Busca vendas com parcela 1 pendente
            vendas_result = supabase.table('vendas').select('*').eq(
                'clinica_id', clinica_id
            ).eq('pagamento_confirmado', True).eq('parcela1_clinica_paga', False).execute()
            
            if not vendas_result.data:
                ui.notification_show("⚠️ Nenhuma parcela 1 pendente!", type="warning")
                return
            
            # Busca comissão
            comissao_result = supabase.table('comissoes_clinica').select('*').eq('clinica_id', clinica_id).execute()
            comissao_config = comissao_result.data[0] if comissao_result.data else {}
            
            total_pago = 0
            vendas_pagas = []
            
            for venda in vendas_result.data:
                valor_venda = float(venda.get('valor_total', 0) or 0)
                
                # Calcula comissão
                if comissao_config.get('tipo') == 'percentual':
                    comissao = valor_venda * (comissao_config.get('valor_percentual', 0) / 100)
                else:
                    comissao = comissao_config.get('valor_fixo', 0)
                
                valor_liquido = valor_venda - comissao
                valor_parcela1 = valor_liquido / 2
                
                # Atualiza venda
                supabase.table('vendas').update({
                    'parcela1_clinica_paga': True,
                    'data_pagamento_parcela1_clinica': datetime.now().isoformat(),
                    'superusuario_pagou_parcela1_id': user['id']
                }).eq('id', venda['id']).execute()
                
                total_pago += valor_parcela1
                vendas_pagas.append(venda['numero_venda'])
            
            print(f"✅ {len(vendas_pagas)} parcelas pagas!")
            print(f"💰 Total: {formatar_moeda(total_pago)}")
            print(f"{'='*60}\n")
            
            ui.notification_show(
                f"✅ Parcela 1 paga com sucesso!\n"
                f"📄 Vendas: {len(vendas_pagas)}\n"
                f"💰 Total: {formatar_moeda(total_pago)}",
                type="message",
                duration=8
            )
            
        except Exception as e:
            print(f"❌ Erro em _monitor_pagar_parcela1: {e}")
            import traceback
            traceback.print_exc()
            ui.notification_show(f"❌ Erro: {str(e)}", type="error")





    # ========== EFFECT: PAGAR PARCELA 2 ==========
    @reactive.Effect
    def _monitor_pagar_parcela2():
        try:
            clinica_id = None
            try:
                clinica_id = input.pagar_parcela2_clinica()
            except:
                return
            
            if not clinica_id or not supabase:
                return
            
            print(f"\n{'='*60}")
            print(f"💸 PAGAR PARCELA 2 - DEBUG")
            print(f"{'='*60}")
            
            user = user_data()
            if not user:
                return
            
            # Busca vendas com parcela 2 pendente E todos atendimentos concluídos
            vendas_result = supabase.table('vendas').select(
                '*, itens_venda(*)'
            ).eq('clinica_id', clinica_id).eq('pagamento_confirmado', True).eq(
                'parcela2_clinica_paga', False
            ).execute()
            
            if not vendas_result.data:
                ui.notification_show("⚠️ Nenhuma parcela 2 pendente!", type="warning")
                return
            
            # Busca comissão
            comissao_result = supabase.table('comissoes_clinica').select('*').eq('clinica_id', clinica_id).execute()
            comissao_config = comissao_result.data[0] if comissao_result.data else {}
            
            total_pago = 0
            vendas_pagas = []
            
            for venda in vendas_result.data:
                # Verifica se TODOS os itens foram atendidos
                itens = venda.get('itens_venda', [])
                if not itens:
                    continue
                
                itens_atendidos = [item for item in itens if item.get('atendido')]
                
                if len(itens_atendidos) != len(itens):
                    # Ainda tem itens não atendidos, pula
                    continue
                
                valor_venda = float(venda.get('valor_total', 0) or 0)
                
                # Calcula comissão
                if comissao_config.get('tipo') == 'percentual':
                    comissao = valor_venda * (comissao_config.get('valor_percentual', 0) / 100)
                else:
                    comissao = comissao_config.get('valor_fixo', 0)
                
                valor_liquido = valor_venda - comissao
                valor_parcela2 = valor_liquido / 2
                
                # Atualiza venda
                supabase.table('vendas').update({
                    'parcela2_clinica_paga': True,
                    'data_pagamento_parcela2_clinica': datetime.now().isoformat(),
                    'superusuario_pagou_parcela2_id': user['id']
                }).eq('id', venda['id']).execute()
                
                total_pago += valor_parcela2
                vendas_pagas.append(venda['numero_venda'])
            
            if not vendas_pagas:
                ui.notification_show("⚠️ Nenhuma venda com todos os atendimentos concluídos!", type="warning")
                return
            
            print(f"✅ {len(vendas_pagas)} parcelas pagas!")
            print(f"💰 Total: {formatar_moeda(total_pago)}")
            print(f"{'='*60}\n")
            
            ui.notification_show(
                f"✅ Parcela 2 paga com sucesso!\n"
                f"📄 Vendas: {len(vendas_pagas)}\n"
                f"💰 Total: {formatar_moeda(total_pago)}",
                type="message",
                duration=8
            )
            
        except Exception as e:
            print(f"❌ Erro em _monitor_pagar_parcela2: {e}")
            import traceback
            traceback.print_exc()
            ui.notification_show(f"❌ Erro: {str(e)}", type="error")


    # ========== GERAR PIX PARA CLÍNICA ==========
    @reactive.Effect
    def _monitor_gerar_pix_clinica():
        """Gera QR Code PIX para pagamento de clínica"""
        try:
            clinica_id = None
            try:
                clinica_id = input.gerar_pix_clinica_id()
            except:
                return
            
            if not clinica_id:
                return
            
            print(f"\n{'='*60}")
            print(f"🔲 GERAR PIX CLÍNICA - DEBUG")
            print(f"{'='*60}")
            
            user = user_data()
            if not user or not supabase:
                return
            
            # Busca dados da clínica
            clinica_result = supabase.table('clinicas').select('*').eq('id', clinica_id).execute()
            
            if not clinica_result.data:
                ui.notification_show("❌ Clínica não encontrada!", type="error")
                return
            
            clinica = clinica_result.data[0]
            
            # Busca dados PIX
            pix_chave = None
            try:
                dados_pix = json.loads(clinica.get('dados_pix', '{}'))
                pix_chave = dados_pix.get('chave')
            except:
                pass
            
            if not pix_chave:
                ui.notification_show("❌ Clínica não possui chave PIX cadastrada!", type="error")
                return
            
            # Busca comissão
            comissao_result = supabase.table('comissoes_clinica').select('*').eq('clinica_id', clinica_id).execute()
            comissao_config = comissao_result.data[0] if comissao_result.data else {}
            
            # Calcula total a pagar (soma parcelas pendentes)
            vendas_result = supabase.table('vendas').select('*, itens_venda(*)').eq(
                'clinica_id', clinica_id
            ).eq('pagamento_confirmado', True).execute()
            
            total_pagar = 0
            
            for venda in vendas_result.data if vendas_result.data else []:
                valor_venda = float(venda.get('valor_total', 0) or 0)
                
                # Calcula comissão
                if comissao_config.get('tipo') == 'percentual':
                    percentual = float(comissao_config.get('valor_percentual', 0))
                    comissao = valor_venda * (percentual / 100)
                else:
                    comissao = float(comissao_config.get('valor_fixo', 0))
                
                valor_liquido = valor_venda - comissao
                valor_parcela = valor_liquido / 2
                
                # Soma parcelas pendentes
                if not venda.get('parcela1_clinica_paga', False):
                    total_pagar += valor_parcela
                
                # Parcela 2 só se todos itens foram atendidos
                itens = venda.get('itens_venda', [])
                if itens:
                    itens_atendidos = [item for item in itens if item.get('atendido')]
                    if len(itens_atendidos) == len(itens) and not venda.get('parcela2_clinica_paga', False):
                        total_pagar += valor_parcela
            
            print(f"💰 Total a pagar via PIX: R$ {total_pagar:.2f}")
            
            if total_pagar == 0:
                ui.notification_show("❌ Nenhum valor a pagar!", type="warning")
                return
            
            # Gera payload PIX
            nome_beneficiario = clinica.get('nome_fantasia') or clinica.get('razao_social', 'Clinica')
            payload_pix = gerar_pix_payload(
                chave=pix_chave,
                valor=total_pagar,
                beneficiario=nome_beneficiario[:25]
            )
            
            # Gera QR Code
            qrcode_base64 = qrcode_base64 = gerar_qr_code(payload_pix)
            
            # Cria modal com QR Code
            modal_html = f'''
            <div id="pix_modal_clinica" style="
                position: fixed; top: 0; left: 0; width: 100%; height: 100%; 
                background: rgba(0,0,0,0.8); z-index: 9999; 
                display: flex; align-items: center; justify-content: center;
            " onclick="this.style.display='none'">
                <div style="
                    background: white; border-radius: 1rem; padding: 2rem; 
                    max-width: 500px; text-align: center;
                " onclick="event.stopPropagation()">
                    <h3 style="color: #10b981; margin-bottom: 1rem;">💳 Pagamento via PIX</h3>
                    <p style="color: #546E7A; margin-bottom: 1rem;">
                        Clínica: <strong>{nome_beneficiario}</strong><br>
                        Valor: <strong>{formatar_moeda(total_pagar)}</strong>
                    </p>
                    
                    <img src="data:image/png;base64,{qrcode_base64}" 
                         style="max-width: 300px; border: 2px solid #e2e8f0; border-radius: 0.5rem; margin: 1rem 0;">
                    
                    <div style="
                        background: #f1f5f9; padding: 1rem; border-radius: 0.5rem; 
                        margin: 1rem 0; word-break: break-all; font-family: monospace; font-size: 0.75rem;
                    ">
                        {payload_pix}
                    </div>
                    
                    <button onclick="
                        navigator.clipboard.writeText('{payload_pix}');
                        this.innerText = '✅ Copiado!';
                        setTimeout(() => this.innerText = '📋 Copiar Código PIX', 2000);
                    " style="
                        background: #10b981; color: white; border: none; 
                        padding: 0.75rem 1.5rem; border-radius: 0.5rem; 
                        font-weight: 600; cursor: pointer; width: 100%; margin-bottom: 0.5rem;
                    ">📋 Copiar Código PIX</button>
                    
                    <button onclick="document.getElementById('pix_modal_clinica').style.display='none'" 
                        style="
                            background: #ef4444; color: white; border: none; 
                            padding: 0.75rem 1.5rem; border-radius: 0.5rem; 
                            font-weight: 600; cursor: pointer; width: 100%;
                        ">❌ Fechar</button>
                </div>
            </div>
            '''
            
            ui.insert_ui(
                selector="body",
                where="beforeEnd",
                ui=ui.HTML(modal_html)
            )
            
            print(f"✅ QR Code PIX gerado!")
            print(f"💰 Valor: {formatar_moeda(total_pagar)}")
            print(f"{'='*60}\n")
            
            ui.notification_show(
                f"✅ QR Code PIX gerado!\n"
                f"💰 Valor: {formatar_moeda(total_pagar)}\n"
                f"🏥 Beneficiário: {nome_beneficiario}",
                type="message",
                duration=8
            )
            
        except Exception as e:
            print(f"❌ Erro em _monitor_gerar_pix_clinica: {e}")
            import traceback
            traceback.print_exc()
            ui.notification_show(f"❌ Erro: {str(e)}", type="error")  


    @output
    @render.ui
    def cliente_codigo_display():
        try:
            codigo = gerar_codigo_cliente()
            print(f"\n🆔 CÓDIGO GERADO: {codigo}")
            print(f"   Tipo: {type(codigo)}")
            print(f"   Tamanho: {len(codigo)}")
            
            return ui.div(
                {"style": "margin-top: 1rem;"},
                ui.tags.label("Código (gerado automaticamente)", 
                             style="font-weight: 600; margin-bottom: 0.5rem; display: block; color: #2D3748;"),
                ui.div(
                    {"style": "background: linear-gradient(135deg, #1DD1A1, #0D9488); padding: 1rem; border-radius: 0.5rem; font-weight: 700; color: white; font-size: 1.2rem; text-align: center; letter-spacing: 2px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);"},
                    codigo
                )
            )
        except Exception as e:
            print(f"❌ Erro em cliente_codigo_display: {e}")
            import traceback
            traceback.print_exc()
            return ui.div(
                ui.p("Erro ao gerar código", style="color: red;")
            )
    #Lista de clínicas
  
    @output
    @render.ui
    def lista_minhas_clinicas():
        """Lista cards com informações das clínicas"""
        try:
            user = user_data()
            if not user or not supabase:
                return ui.div(
                    {"style": "text-align: center; padding: 3rem;"},
                    ui.h5("😔 Nenhuma clínica cadastrada", style="color: #546E7A;")
                )
            result = supabase.table('clinicas').select(
                '*, usuario_info:usuarios!clinicas_usuario_id_fkey(email)'
            ).eq('vendedor_id', user['id']).order('criado_em', desc=True).execute()
            
            if not result.data:
                return ui.div(
                    {"style": "text-align: center; padding: 3rem;"},
                    ui.h5("😔 Você ainda não cadastrou nenhuma clínica", style="color: #546E7A;"),
                    ui.p("Vá para 'Cadastrar Clínica' para começar!", style="color: #94a3b8;")
                )
            
            cards = []
            for clinica in result.data:
                status_color = "#10b981" if clinica.get('ativo') else "#ef4444"
                status_text = "✅ Ativa" if clinica.get('ativo') else "❌ Inativa"
                
                comissao_text = "A definir"
                try:
                    com_result = supabase.table('comissoes_clinica').select('*').eq('clinica_id', clinica['id']).execute()
                    if com_result.data:
                        com = com_result.data[0]
                        if com.get('tipo') == 'percentual':
                            comissao_text = f"{com.get('valor_percentual', 0)}%"
                        else:
                            comissao_text = formatar_moeda(com.get('valor_fixo', 0))
                except:
                    pass
    
                email_login_clinica = clinica.get('usuario_info', {}).get('email', '-')
                data_criacao = clinica.get('criado_em')
                data_formatada = pd.to_datetime(data_criacao).strftime('%d/%m/%Y') if pd.notna(data_criacao) else "Data N/D"
    
                card = ui.div(
                    {"class": "card-custom", "style": f"margin-bottom: 1rem; border-left: 4px solid {status_color}"},
                    ui.row(
                        ui.column(9,
                            ui.h5(clinica.get('razao_social', 'Sem nome'), style="margin: 0 0 0.5rem 0; color: #2D3748;"),
                            ui.p(f"🏢 {clinica.get('nome_fantasia', '-')}", style="margin: 0 0 1rem 0; color: #546E7A;"),
                            ui.row(
                                ui.column(4,
                                    # Sintaxe correta: argumentos posicionais primeiro
                                    ui.p(ui.tags.strong("CNPJ: "), formatar_cnpj(clinica.get('cnpj', '')), style="margin: 0.25rem 0; font-size: 0.9rem;"),
                                    ui.p(ui.tags.strong("WhatsApp: "), formatar_whatsapp(clinica.get('whatsapp', '-')), style="margin: 0.25rem 0; font-size: 0.9rem;")
                                ),
                                ui.column(4,
                                    # Sintaxe correta: argumentos posicionais primeiro
                                    ui.p(ui.tags.strong("Cidade: "), f"{clinica.get('endereco_cidade', '-')}/{clinica.get('endereco_estado', '-')}", style="margin: 0.25rem 0; font-size: 0.9rem;"),
                                    ui.p(ui.tags.strong("Responsável: "), clinica.get('responsavel_nome', '-'), style="margin: 0.25rem 0; font-size: 0.9rem;")
                                ),
                                ui.column(4,
                                    # Sintaxe correta: argumentos posicionais primeiro
                                    ui.p(ui.tags.strong("Comissão: "), comissao_text, style="margin: 0.25rem 0; font-size: 0.9rem;"),
                                    ui.p(ui.tags.strong("Email Login: "), email_login_clinica, style="margin: 0.25rem 0; font-size: 0.9rem;")
                                )
                            )
                        ),
                        ui.column(3,
                            ui.div(
                                {"style": "text-align: center; padding: 1rem;"},
                                ui.div(
                                    {"style": f"background: {status_color}; color: white; border-radius: 0.5rem; padding: 0.5rem; margin-bottom: 0.5rem;"},
                                    ui.p(status_text, style="margin: 0; font-weight: 600; font-size: 0.9rem;")
                                ),
                                ui.p(f"📅 {data_formatada}", style="margin: 0; font-size: 0.85rem; color: #546E7A;")
                            )
                        )
                    )
                )
                cards.append(card)
            
            return ui.div(*cards)
            
        except Exception as e:
            print(f"Erro lista_minhas_clinicas: {e}")
            import traceback
            traceback.print_exc()
            return ui.div(ui.p(f"❌ Erro: {str(e)}", style="color: #ef4444;"))
    
    @output
    @render.ui
    def btn_converter_wrapper():
        try:
            user = user_data()
            if not user or not supabase:
                return ui.p("")
            
            result = supabase.table('vendas').select('id', count='exact').eq('vendedor_id', user['id']).eq('tipo', 'orcamento').execute()
            
            if not result.data or result.count == 0:
                return ui.p("Nenhum orçamento", style="font-size: 0.9rem; margin: 0; opacity: 0.8;")
            
            return ui.div(
                ui.output_ui("select_orcamento_inline"),
                ui.input_action_button("btn_converter_orcamento", "✅ Converter",
                                      class_="btn btn-light w-100 mt-2",
                                      style="font-weight: 600;")
            )
        except:
            return ui.p("")
    
    @output
    @render.ui
    def select_orcamento_inline():
        try:
            user = user_data()
            if not user or not supabase:
                return ui.div()
            
            result = supabase.table('vendas').select('id, numero_venda, valor_total').eq('vendedor_id', user['id']).eq('tipo', 'orcamento').limit(10).order('criado_em', desc=True).execute()
            
            if not result.data:
                return ui.div()
            
            choices = {
                str(v['id']): f"{v['numero_venda']} - {formatar_moeda(v['valor_total'])}"
                for v in result.data
            }
            return ui.input_select("orcamento_id", "", choices=choices)
        except:
            return ui.div()
    

    # ========== FUNÇÃO DE SEGURANÇA ==========
    def safe_str(value):
        """Converte qualquer valor para string de forma segura"""
        if value is None:
            return "0"
        if isinstance(value, (int, float)):
            return str(value)
        if isinstance(value, str):
            return value
        try:
            return str(value)
        except:
            return "0"

    @output
    @render.text
    def stat_minhas_clinicas():
        try:
            user = user_data()
            if not user or not supabase: return "0"
            result = supabase.table('clinicas').select('id', count='exact').eq('vendedor_id', user['id']).eq('ativo', True).execute()
            return str(result.count or 0)
        except: return "0"
    
    @output
    @render.text
    def stat_vendas_minhas_clinicas():
        try:
            user = user_data()
            if not user or not supabase: return "0"
            result = supabase.table('vendas').select('id', count='exact').eq('vendedor_id', user['id']).eq('tipo', 'venda').execute()
            return str(result.count or 0)
        except: return "0"
    
    @output
    @render.text
    def stat_faturamento_minhas_clinicas():
        try:
            user = user_data()
            if not user or not supabase: return "R$ 0,00"
            result = supabase.table('vendas').select('valor_total').eq('vendedor_id', user['id']).eq('tipo', 'venda').execute()
            if not result.data: return "R$ 0,00"
            total = sum([float(v['valor_total']) for v in result.data if v.get('valor_total')]) or 0
            return str(formatar_moeda(total))
        except: return "R$ 0,00"       


    # Cadastros    
    
    @reactive.Effect
    @reactive.event(input.btn_add_clinica)
    def add_clinica():
        try:
            # Validações iniciais
            if not supabase:
                ui.notification_show("❌ Supabase não configurado", type="error")
                return
            
            user = user_data()
            if not user:
                ui.notification_show("❌ Usuário não autenticado", type="error")
                return
            
            # Coleta dados do formulário
            razao = input.cli_razao()
            cnpj = input.cli_cnpj()
            whatsapp = input.cli_whatsapp()
            cidade = input.cli_cidade()
            uf = input.cli_uf()
            senha = input.cli_senha()
            
            # ========== DEBUG DA SENHA ==========
            print("\n" + "="*60)
            print("🔐 DEBUG - CADASTRO DE CLÍNICA")
            print("="*60)
            print(f"Senha digitada: '{senha}'")
            print(f"Tipo: {type(senha)}")
            print(f"Tamanho: {len(senha)}")
            print(f"Repr: {repr(senha)}")
            # ====================================
            
            # Validações básicas
            if not all([razao, cnpj, whatsapp, cidade, uf, senha]):
                ui.notification_show("⚠️ Preencha os campos obrigatórios!", type="warning")
                return
            
            if len(senha) < 6:
                ui.notification_show("⚠️ A senha deve ter no mínimo 6 caracteres!", type="warning")
                return
            
            # Limpa e valida CNPJ
            cnpj_limpo = limpar_documento(cnpj)
            
            if not validar_cnpj(cnpj_limpo):
                ui.notification_show("⚠️ CNPJ inválido!", type="warning")
                return
            
            # Verifica duplicidade
            check_user = supabase.table('usuarios').select('id').eq('cpf', cnpj_limpo).execute()
            if check_user.data:
                ui.notification_show("⚠️ Este CNPJ já está cadastrado!", type="warning")
                return
            
            # Processa logo
            logo_url = None
            file_info = input.cli_logo()
            if file_info:
                try:
                    file = file_info[0]
                    file_path = file['datapath']
                    with open(file_path, 'rb') as f:
                        logo_bytes = f.read()
                        logo_base64 = base64.b64encode(logo_bytes).decode()
                        logo_url = f"data:image/jpeg;base64,{logo_base64}"
                except Exception as e:
                    print(f"Erro ao processar logo: {e}")
            
            # Dados bancários
            dados_bancarios = {
                "banco": input.cli_banco(),
                "agencia": input.cli_agencia(),
                "conta": input.cli_conta(),
                "pix": input.cli_pix(),
                "titular": input.cli_titular()
            }
            # Dados PIX
            dados_pix = {
                "chave": input.cli_pix_chave(),
                "tipo": input.cli_pix_tipo()
            }

            # Na criação da clínica, adicione:
            clinica_data = {
                # ... campos existentes ...
                "dados_bancarios": json.dumps(dados_bancarios),
                "dados_pix": json.dumps(dados_pix),  # ← NOVO
                "vendedor_id": user['id'],
                "whatsapp": input.cli_whatsapp(),
                "ativo": True
            }
            
            # ========== CRIA HASH DA SENHA ==========
            senha_limpa = senha.strip()
            senha_hash = hash_senha(senha_limpa)
            
            print(f"\n🔐 HASH GERADO:")
            print(f"Senha após strip: '{senha_limpa}'")
            print(f"Hash gerado: {senha_hash[:30]}...")
            print(f"Hash completo: {senha_hash}")
            print("="*60 + "\n")
            # ========================================
            
            # Cria usuário
            usuario_data_clinica = {
                "id": str(uuid.uuid4()),
                "nome": razao,
                "email": f"{cnpj_limpo}@medpix.local",
                "cpf": cnpj_limpo,
                "senha_hash": senha_hash,  # ✅ USA O HASH
                "tipo_usuario": "clinica",
                "ativo": True
            }
            
            usuario_result = supabase.table('usuarios').insert(usuario_data_clinica).execute()
            
            if not usuario_result.data:
                ui.notification_show("❌ Erro ao criar usuário!", type="error")
                return
            
            usuario_id = usuario_result.data[0]['id']
            
            # Cria clínica
            clinica_data = {
                "usuario_id": usuario_id,
                "razao_social": razao,
                "nome_fantasia": input.cli_fantasia(),
                "cnpj": cnpj_limpo,
                "email": input.cli_email(),
                "telefone": input.cli_telefone(),
                "endereco_rua": input.cli_endereco(),
                "endereco_cidade": cidade,
                "endereco_estado": uf,
                "responsavel_nome": input.cli_responsavel(),
                "responsavel_contato": input.cli_resp_contato(),
                "logo_url": logo_url,
                "dados_bancarios": json.dumps(dados_bancarios),
                "vendedor_id": user['id'],
                "whatsapp": input.cli_whatsapp(),
                "ativo": True
            }
            
            clinica_result = supabase.table('clinicas').insert(clinica_data).execute()
            
            if not clinica_result.data:
                ui.notification_show("❌ Erro ao cadastrar clínica!", type="error")
                return
            
            clinica_id = clinica_result.data[0]['id']
            
            # Cria comissão
            tipo_comissao = input.cli_tipo_comissao()
            comissao_data = {
                "clinica_id": clinica_id,
                "tipo": tipo_comissao
            }
            # Cria cashback
            cashback_perc = input.cli_cashback_perc()
            if cashback_perc and cashback_perc > 0:
                cashback_data = {
                    "clinica_id": clinica_id,
                    "percentual": cashback_perc
                }
                supabase.table('cashback_clinica').insert(cashback_data).execute()
                print(f"✅ Cashback configurado: {cashback_perc}%")
            
            if tipo_comissao == "percentual":
                comissao_data["valor_percentual"] = input.cli_comissao_perc()
            else:
                comissao_data["valor_fixo"] = input.cli_comissao_valor()
            
            supabase.table('comissoes_clinica').insert(comissao_data).execute()
            
            # Prepara dados para contrato
            clinica_completa = {
                **clinica_result.data[0],
                'comissao_tipo': tipo_comissao,
                'comissao_perc': input.cli_comissao_perc() if tipo_comissao == 'percentual' else None,
                'comissao_valor': input.cli_comissao_valor() if tipo_comissao == 'valor' else None
            }
            
            # Gera contrato
            try:
                pdf_bytes = gerar_contrato_parceria(
                    clinica_completa,
                    formatar_cnpj(cnpj_limpo),
                    senha_limpa,  # ✅ PASSA A SENHA ORIGINAL (não o hash)
                    user.get('nome', 'Vendedor')
                )
                
                ultimo_contrato.set({
                    'pdf': pdf_bytes,
                    'filename': f"Contrato_{razao.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.pdf",
                    'clinica': razao,
                    'usuario': formatar_cnpj(cnpj_limpo),
                    'senha': senha_limpa
                })
                
                ui.notification_show(
                    f"✅ Clínica cadastrada com sucesso!\n🏥 CNPJ: {formatar_cnpj(cnpj_limpo)}\n🔑 Senha: {senha_limpa}\n📄 Contrato gerado!",
                    type="message",
                    duration=15
                )
                
                limpar_form_clinica()
                clinicas_trigger.set(clinicas_trigger() + 1)
                
            except Exception as e:
                print(f"Erro ao gerar contrato: {e}")
                ui.notification_show(
                    f"⚠️ Clínica cadastrada, mas erro ao gerar contrato: {str(e)}",
                    type="warning"
                )
        
        except Exception as e:
            print(f"Erro em add_clinica: {e}")
            import traceback
            traceback.print_exc()
            ui.notification_show(f"❌ Erro: {str(e)}", type="error")
    
    @reactive.Effect
    @reactive.event(input.btn_add_cliente)
    def add_cliente():
        try:
            if not supabase:
                ui.notification_show("❌ Supabase não configurado", type="error")
                return
            
            user = user_data()
            if not user:
                ui.notification_show("❌ Usuário não autenticado", type="error")
                return
            
            nome = input.cliente_nome()
            cpf = input.cliente_cpf()
            cidade = input.cliente_cidade()
            uf = input.cliente_uf()
            
            if not all([nome, cpf, cidade, uf]):
                ui.notification_show("⚠️ Preencha os campos obrigatórios!", type="warning")
                return
            
            cpf_limpo = ''.join(filter(str.isdigit, cpf))
            codigo = gerar_codigo_cliente()
            
            # ========== UPLOAD DA FOTO PARA SUPABASE STORAGE ==========
            foto_url = None
            file_info = input.cliente_foto()
            
            if file_info:
                try:
                    print("\n" + "="*60)
                    print("📸 UPLOAD DE FOTO - DEBUG")
                    print("="*60)
                    
                    file = file_info[0]
                    file_path = file['datapath']
                    file_name_original = file['name']
                    
                    print(f"📁 Arquivo: {file_name_original}")
                    print(f"📂 Path: {file_path}")
                    
                    # Lê o arquivo
                    with open(file_path, 'rb') as f:
                        foto_bytes = f.read()
                    
                    print(f"📊 Tamanho: {len(foto_bytes)} bytes")
                    
                    # Gera nome único para o arquivo
                    import time
                    timestamp = int(time.time())
                    extensao = file_name_original.split('.')[-1].lower()
                    nome_arquivo = f"{cpf_limpo}_{timestamp}.{extensao}"
                    
                    print(f"📝 Nome no storage: {nome_arquivo}")
                    
                    # Upload para Supabase Storage
                    bucket_name = os.environ.get("SUPABASE_BUCKET_NAME", "fotos-clientes")
                    
                    print(f"📦 Bucket: {bucket_name}")
                    print(f"⬆️ Fazendo upload...")
                    
                    # Remove arquivo anterior se existir
                    try:
                        supabase.storage.from_(bucket_name).remove([nome_arquivo])
                    except:
                        pass
                    
                    # Faz upload
                    result = supabase.storage.from_(bucket_name).upload(
                        path=nome_arquivo,
                        file=foto_bytes,
                        file_options={
                            "content-type": f"image/{extensao}",
                            "cache-control": "3600",
                            "upsert": "true"
                        }
                    )
                    
                    print(f"✅ Upload concluído!")
                    print(f"📊 Resultado: {result}")
                    
                    # Gera URL pública
                    foto_url = supabase.storage.from_(bucket_name).get_public_url(nome_arquivo)
                    
                    print(f"🔗 URL pública: {foto_url}")
                    print("="*60 + "\n")
                    
                    ui.notification_show("✅ Foto enviada com sucesso!", type="message", duration=3)
                    
                except Exception as e:
                    print(f"❌ Erro ao fazer upload da foto: {e}")
                    import traceback
                    traceback.print_exc()
                    ui.notification_show(f"⚠️ Erro ao enviar foto: {str(e)}", type="warning")
                    # Continua o cadastro mesmo sem foto
            
            # ========== CADASTRA O CLIENTE ==========
            data = {
                "nome_completo": nome,
                "cpf": cpf_limpo,
                "codigo": codigo,
                "telefone": input.cliente_telefone(),
                "email": input.cliente_email(),
                "endereco_rua": input.cliente_endereco(),
                "endereco_cidade": cidade,
                "endereco_estado": uf,
                "foto_url": foto_url,  # URL do Storage ou None                
                "ativo": True
            }
            
            result = supabase.table('clientes').insert(data).execute()
            
            ui.notification_show(
                f"✅ Cliente cadastrado!\n"
                f"🆔 Código: {codigo}\n"
                f"{'📸 Foto salva!' if foto_url else ''}",
                type="message", 
                duration=5
            )
            
            limpar_form_cliente()
            clientes_trigger.set(clientes_trigger() + 1)
            data_changed_trigger.set(data_changed_trigger() + 1)
            
        except Exception as e:
            print(f"❌ Erro em add_cliente: {e}")
            import traceback
            traceback.print_exc()
            ui.notification_show(f"❌ Erro: {str(e)}", type="error")
    
    @output
    @render.ui
    def preview_foto_cliente():
        """Mostra prévia da foto selecionada"""
        try:
            file_info = input.cliente_foto()
            if not file_info:
                return ui.div()
            
            file = file_info[0]
            file_path = file['datapath']
            
            # Lê e converte para base64
            with open(file_path, 'rb') as f:
                foto_bytes = f.read()
                foto_base64 = base64.b64encode(foto_bytes).decode()
            
            return ui.div(
                {"class": "mt-3 p-3", "style": "background: #f8fafc; border-radius: 0.5rem; text-align: center;"},
                ui.h6("📸 Prévia da Foto", style="margin-bottom: 1rem;"),
                ui.HTML(f'<img src="data:image/jpeg;base64,{foto_base64}" style="max-width: 200px; max-height: 200px; border-radius: 0.5rem; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">'),
                ui.p(f"📁 {file['name']}", style="margin-top: 0.5rem; font-size: 0.85rem; color: #546E7A;")
            )
        except:
            return ui.div()

    def verificar_vinculo_clinica(user_id):
        """Função auxiliar para diagnosticar problemas de vínculo"""
        try:
            print("\n" + "="*60)
            print("🔍 DIAGNÓSTICO DE VÍNCULO - DEBUG")
            print("="*60)
            
            # 1. Busca usuário
            user_result = supabase.table('usuarios').select('*').eq('id', user_id).execute()
            if user_result.data:
                user = user_result.data[0]
                print(f"✅ Usuário encontrado:")
                print(f"   - Nome: {user.get('nome')}")
                print(f"   - Tipo: {user.get('tipo_usuario')}")
                print(f"   - ID: {user.get('id')}")
            
            # 2. Busca clínica por usuario_id
            clinica_result = supabase.table('clinicas').select('*').eq('usuario_id', user_id).execute()
            if clinica_result.data:
                print(f"\n✅ Clínica vinculada encontrada:")
                for c in clinica_result.data:
                    print(f"   - Razão Social: {c.get('razao_social')}")
                    print(f"   - ID: {c.get('id')}")
                    print(f"   - Usuario ID: {c.get('usuario_id')}")
            else:
                print(f"\n❌ Nenhuma clínica vinculada a este usuario_id")
                
                # 3. Lista TODAS as clínicas
                todas = supabase.table('clinicas').select('id, razao_social, usuario_id').execute()
                print(f"\n📋 Todas as clínicas no sistema:")
                if todas.data:
                    for c in todas.data:
                        print(f"   - {c.get('razao_social')}")
                        print(f"     Usuario ID: {c.get('usuario_id')}")
                
            print("="*60 + "\n")
            
        except Exception as e:
            print(f"❌ Erro no diagnóstico: {e}")
   
    @reactive.Effect
    @reactive.event(input.btn_add_proc)
    def add_procedimento():
        try:
            print("\n" + "="*60)
            print("🔬 CADASTRO DE PROCEDIMENTO - DEBUG")
            print("="*60)
            
            if not supabase:
                ui.notification_show("❌ Supabase não configurado", type="error")
                return
            
            user = user_data()
            if not user:
                print("❌ Usuário não autenticado")
                ui.notification_show("❌ Usuário não autenticado", type="error")
                return
            
            print(f"👤 Usuário: {user.get('nome')}")
            print(f"🔑 Tipo: {user.get('tipo_usuario')}")
            print(f"🆔 User ID: {user.get('id')}")
            
            # Busca clínica
            print("\n🔍 Buscando clínica...")
            clinica_result = supabase.table('clinicas').select('*').eq('usuario_id', user['id']).execute()
            
            print(f"📊 Resultado da busca:")
            print(f"   - Dados retornados: {len(clinica_result.data) if clinica_result.data else 0}")
            
            if clinica_result.data:
                print(f"   - Clínica encontrada: {clinica_result.data[0].get('razao_social')}")
                print(f"   - Clínica ID: {clinica_result.data[0].get('id')}")
            else:
                print("   - ❌ Nenhuma clínica encontrada")
                print(f"\n🔍 DIAGNÓSTICO:")
                print(f"   Tentando buscar com usuario_id = '{user['id']}'")
                
                # Busca TODAS as clínicas para debug
                todas_clinicas = supabase.table('clinicas').select('id, razao_social, usuario_id').execute()
                print(f"\n📋 Clínicas cadastradas no sistema:")
                if todas_clinicas.data:
                    for c in todas_clinicas.data:
                        print(f"   - {c.get('razao_social')} (usuario_id: {c.get('usuario_id')})")
                else:
                    print("   - Nenhuma clínica cadastrada")
                
                ui.notification_show(
                    "❌ Clínica não encontrada!\n"
                    "Verifique se esta conta está vinculada a uma clínica.\n"
                    "Contate o administrador se necessário.",
                    type="error",
                    duration=8
                )
                return
            
            clinica_id = clinica_result.data[0]['id']
            
            # Coleta dados do formulário
            nome = input.proc_nome()
            grupo = input.proc_grupo()
            preco = input.proc_preco()
            
            print(f"\n📝 Dados do procedimento:")
            print(f"   - Nome: {nome}")
            print(f"   - Grupo: {grupo}")
            print(f"   - Preço: {preco}")
            
            if not all([nome, grupo, preco]):
                ui.notification_show("⚠️ Preencha os campos obrigatórios!", type="warning")
                return
                
            # ========== VALIDAÇÃO DE DUPLICIDADE ==========
            # Normaliza o nome para comparação (remove espaços extras e case-insensitive)
            nome_normalizado = nome.strip().lower()
            
            # Busca procedimentos da clínica
            procedimentos_existentes = supabase.table('procedimentos').select(
                'id, nome'
            ).eq('clinica_id', clinica_id).execute()
            
            # Verifica se já existe um procedimento com nome similar
            for proc_existente in procedimentos_existentes.data if procedimentos_existentes.data else []:
                nome_existente_normalizado = proc_existente.get('nome', '').strip().lower()
                if nome_existente_normalizado == nome_normalizado:
                    ui.notification_show(
                        f"⚠️ Já existe um procedimento com este nome!\n"
                        f"Nome cadastrado: {proc_existente.get('nome')}\n"
                        f"Se for diferente, altere ligeiramente o nome.",
                        type="warning",
                        duration=8
                    )
                    return
            # =============================================
            
            # Insere procedimento
            data = {
                "clinica_id": clinica_id,
                "nome": nome,
                "grupo_id": grupo,
                "preco": preco,
                "descricao": input.proc_descricao(),
                "ativo": True
            }
            
            print(f"\n💾 Inserindo procedimento no banco...")
            result = supabase.table('procedimentos').insert(data).execute()
            
            if result.data:
                print(f"✅ Procedimento cadastrado com sucesso!")
                print("="*60 + "\n")
                
                ui.notification_show("✅ Procedimento cadastrado com sucesso!", type="message")
                
                # Limpar e atualizar
                limpar_form_procedimento()
                procedimentos_trigger.set(procedimentos_trigger() + 1)
            else:
                print(f"❌ Erro ao inserir procedimento")
                print("="*60 + "\n")
                ui.notification_show("❌ Erro ao cadastrar procedimento", type="error")
                
        except Exception as e:
            print(f"\n❌ ERRO em add_procedimento: {e}")
            import traceback
            traceback.print_exc()
            print("="*60 + "\n")
            ui.notification_show(f"❌ Erro: {str(e)}", type="error")
    
    @reactive.Effect
    @reactive.event(input.btn_import_proc)
    def importar_procedimentos():
        try:
            file_info = input.upload_proc()
            if not file_info:
                ui.notification_show("⚠️ Selecione um arquivo!", type="warning")
                return
            
            user = user_data()
            if not user or not supabase:
                return
            
            clinica_result = supabase.table('clinicas').select('id').eq('usuario_id', user['id']).execute()
            if not clinica_result.data:
                ui.notification_show("❌ Clínica não encontrada", type="error")
                return
            
            clinica_id = clinica_result.data[0]['id']
            
            # Lê o arquivo
            file = file_info[0]
            print(f"\n📄 Importando arquivo: {file['name']}")
            
            if file['name'].endswith('.csv'):
                df = pd.read_csv(file['datapath'])
            else:
                df = pd.read_excel(file['datapath'])
            
            # ========== NORMALIZA NOMES DAS COLUNAS ==========
            # Remove espaços, converte para minúsculas
            df.columns = df.columns.str.strip().str.lower()
            
            print(f"\n🔍 Colunas encontradas na planilha:")
            for col in df.columns:
                print(f"   - '{col}'")
            
            # Aceita variações dos nomes
            mapeamento_colunas = {
                'nome': ['nome', 'procedimento', 'nome_procedimento', 'exame'],
                'grupo': ['grupo', 'categoria', 'tipo', 'grupo_procedimento'],
                'preco': ['preco', 'preço', 'valor', 'price']
            }
            
            # Encontra as colunas corretas
            col_nome = None
            col_grupo = None
            col_preco = None
            
            for col in df.columns:
                for variacao in mapeamento_colunas['nome']:
                    if variacao in col:
                        col_nome = col
                        break
                for variacao in mapeamento_colunas['grupo']:
                    if variacao in col:
                        col_grupo = col
                        break
                for variacao in mapeamento_colunas['preco']:
                    if variacao in col:
                        col_preco = col
                        break
            
            # Valida se encontrou todas
            if not all([col_nome, col_grupo, col_preco]):
                faltando = []
                if not col_nome: faltando.append("nome/procedimento")
                if not col_grupo: faltando.append("grupo/categoria")
                if not col_preco: faltando.append("preco/valor")
                
                ui.notification_show(
                    f"❌ Colunas não encontradas: {', '.join(faltando)}\n"
                    f"📋 Colunas na planilha: {', '.join(df.columns)}",
                    type="error",
                    duration=10
                )
                return
            
            print(f"\n✅ Mapeamento de colunas:")
            print(f"   Nome: '{col_nome}'")
            print(f"   Grupo: '{col_grupo}'")
            print(f"   Preço: '{col_preco}'")
            
            # ========== BUSCA GRUPOS NO BANCO ==========
            grupos_result = supabase.table('grupos_procedimentos').select('id, nome').execute()
            if not grupos_result.data:
                ui.notification_show("❌ Nenhum grupo cadastrado! Cadastre grupos primeiro.", type="error")
                return
            
            # Cria mapa (normalizado para comparação)
            grupos_map = {}
            for g in grupos_result.data:
                grupo_nome_normalizado = g['nome'].lower().strip()
                grupos_map[grupo_nome_normalizado] = g['id']
            
            print(f"\n📋 Grupos disponíveis no sistema:")
            for nome in grupos_map.keys():
                print(f"   - '{nome}'")
            
            # ========== PROCESSA LINHAS ==========
            count_sucesso = 0
            count_erro = 0
            erros = []
            
            for idx, row in df.iterrows():
                try:
                    # Extrai dados
                    nome_proc = str(row[col_nome]).strip()
                    grupo_nome = str(row[col_grupo]).strip().lower()
                    preco_str = str(row[col_preco]).strip()
                    
                    # Pula linhas vazias
                    if not nome_proc or nome_proc.lower() in ['nan', 'none', '']:
                        continue
                    
                    # Remove símbolos de moeda e converte preço
                    preco_str = preco_str.replace('R$', '').replace('r$', '')
                    preco_str = preco_str.replace('.', '').replace(',', '.')
                    preco = float(preco_str)
                    
                    # Busca grupo
                    grupo_id = grupos_map.get(grupo_nome)
                    
                    if not grupo_id:
                        erros.append(f"Linha {idx+2}: Grupo '{row[col_grupo]}' não encontrado")
                        count_erro += 1
                        continue
                    
                    # Insere no banco
                    data = {
                        "clinica_id": clinica_id,
                        "nome": nome_proc,
                        "grupo_id": grupo_id,
                        "preco": preco,
                        "ativo": True
                    }
                    
                    supabase.table('procedimentos').insert(data).execute()
                    count_sucesso += 1
                    print(f"   ✅ {nome_proc} - {preco}")
                    
                except Exception as e:
                    count_erro += 1
                    erros.append(f"Linha {idx+2}: {str(e)}")
                    print(f"   ❌ Erro linha {idx+2}: {e}")
            
            # ========== RESULTADO ==========
            if count_sucesso > 0:
                ui.notification_show(
                    f"✅ {count_sucesso} procedimento(s) importado(s)!\n"
                    f"❌ {count_erro} erro(s)",
                    type="message" if count_erro == 0 else "warning",
                    duration=8
                )
                
                # Atualiza tabela
                procedimentos_trigger.set(procedimentos_trigger() + 1)
            else:
                ui.notification_show(
                    f"❌ Nenhum procedimento importado!\n"
                    f"Erros: {len(erros)}",
                    type="error",
                    duration=8
                )
            
            # Mostra erros detalhados
            if erros and len(erros) <= 10:
                print(f"\n❌ Erros detalhados:")
                for erro in erros:
                    print(f"   {erro}")
            
        except Exception as e:
            print(f"\n❌ ERRO CRÍTICO na importação: {e}")
            import traceback
            traceback.print_exc()
            ui.notification_show(f"❌ Erro: {str(e)}", type="error")
    
    # Carrinho e vendas
    @reactive.Effect
    @reactive.event(input.btn_add_carrinho)
    def adicionar_ao_carrinho():
        try:
            if not input.venda_proc():
                ui.notification_show("⚠️ Selecione um procedimento!", type="warning")
                return
            
            proc_id = input.venda_proc()
            qtd = input.venda_qtd()
            
            result = supabase.table('procedimentos').select('*').eq('id', proc_id).execute()
            if not result.data:
                return
            
            proc = result.data[0]
            item = {
                "procedimento_id": proc_id,
                "nome": proc['nome'],
                "quantidade": qtd,
                "preco_unitario": float(proc['preco']),
                "preco_total": qtd * float(proc['preco'])
            }
            
            items = carrinho() + [item]
            carrinho.set(items)
            ui.notification_show("✅ Item adicionado ao carrinho!", type="message")
            
        except Exception as e:
            ui.notification_show(f"❌ Erro: {str(e)}", type="error")
    
    @output
    @render.data_frame
    def tabela_carrinho():
        items = carrinho()
        if not items:
            return pd.DataFrame({"Mensagem": ["Carrinho vazio"]})
        
        df = pd.DataFrame(items)
        df['preco_unitario'] = df['preco_unitario'].apply(formatar_moeda)
        df['preco_total'] = df['preco_total'].apply(formatar_moeda)
        df.columns = ['ID', 'Procedimento', 'Qtd', 'Preço Unit.', 'Total']
        return df[['Procedimento', 'Qtd', 'Preço Unit.', 'Total']]
    
    @output
    @render.text
    def carrinho_total():
        try:
            items = carrinho()
            if not items:
                return "R$ 0,00"
            total = sum([item.get('preco_total', 0) for item in items])
            return formatar_moeda(total)
        except Exception as e:
            print(f"Erro carrinho_total: {e}")
            return "R$ 0,00"
    
    @reactive.Effect
    @reactive.event(input.btn_finalizar_venda)
    def finalizar_venda():
        try:
            items = carrinho()
            if not items:
                ui.notification_show("⚠️ Carrinho vazio!", type="warning")
                return
            
            if not all([input.venda_tipo(), input.venda_clinica(), input.venda_cliente()]):
                ui.notification_show("⚠️ Preencha todos os campos!", type="warning")
                return
            
            user = user_data()
            if not user or not supabase:
                return
            
            # Busca dados do cliente
            cliente_result = supabase.table('clientes').select('*').eq('id', input.venda_cliente()).execute()
            if not cliente_result.data:
                ui.notification_show("❌ Cliente não encontrado!", type="error")
                return
            cliente_data = cliente_result.data[0]
            
            # Busca dados da clínica
            clinica_result = supabase.table('clinicas').select('*').eq('id', input.venda_clinica()).execute()
            if not clinica_result.data:
                ui.notification_show("❌ Clínica não encontrada!", type="error")
                return
            clinica_data = clinica_result.data[0]
            
            # Gera número da venda e QR code
            numero_venda = gerar_numero_venda()
            total = sum([item['preco_total'] for item in items])
            qr_code = gerar_qr_code(f"VENDA:{numero_venda}")
            
            # Cria venda
            venda_data = {
                "numero_venda": numero_venda,
                "tipo": input.venda_tipo(),
                "vendedor_id": user['id'],
                "cliente_id": input.venda_cliente(),
                "clinica_id": input.venda_clinica(),
                "valor_total": total,
                "qr_code": qr_code,
                "status": "concluido"
            }
            
            venda_result = supabase.table('vendas').insert(venda_data).execute()
            if not venda_result.data:
                ui.notification_show("❌ Erro ao criar venda!", type="error")
                return
            
            venda_id = venda_result.data[0]['id']
            venda_completa = venda_result.data[0]
            
            # Insere itens
            for item in items:
                item_data = {
                    "venda_id": venda_id,
                    "procedimento_id": item['procedimento_id'],
                    "nome_procedimento": item['nome'],
                    "quantidade": item['quantidade'],
                    "preco_unitario": item['preco_unitario'],
                    "preco_total": item['preco_total']
                }
                supabase.table('itens_venda').insert(item_data).execute()
            
            # ========== GERA A IMAGEM (BLOCO CORRIGIDO) ==========
            print("\n" + "="*60)
            print("🖼️ INICIANDO GERAÇÃO DA IMAGEM DA VENDA")
            print("="*60)

            try:
                print(f"1️⃣ Dados da venda: {numero_venda}")
                print(f"2️⃣ Cliente: {cliente_data.get('nome_completo')}")
                print(f"3️⃣ Clínica: {clinica_data.get('razao_social')}")
                print(f"4️⃣ Total de itens: {len(items)}")
                
                # Gera a imagem em bytes
                img_bytes = gerar_imagem_venda(venda_completa, cliente_data, clinica_data, items)
                
                print(f"5️⃣ Imagem gerada! Tamanho: {len(img_bytes)} bytes")
                
                # Armazena os dados da imagem para o download
                ultima_venda_pdf.set({
                    'pdf': img_bytes,
                    'filename': f"Venda_{numero_venda}.png",
                    'numero_venda': numero_venda,
                    'tipo': input.venda_tipo(),
                    'venda_id': venda_id, # ID para futuras consultas
                    'clinica_nome': clinica_data.get('nome_fantasia') or clinica_data.get('razao_social'),
                    'itens': items # Lista de procedimentos
                })
                
                print(f"6️⃣ Dados da imagem armazenados para download.")
                
                # ATIVA O GATILHO PARA MOSTRAR O BOTÃO DE DOWNLOAD
                # Faça isso APENAS se a imagem foi gerada com sucesso
                pdf_trigger.set(pdf_trigger() + 1)
                print(f"7️⃣ Gatilho disparado para exibir o botão! Valor: {pdf_trigger()}")
                print("="*60 + "\n")

                # Limpa o carrinho e notifica o sucesso APENAS se tudo deu certo
                carrinho.set([])
                tipo_texto = "Venda" if input.venda_tipo() == "venda" else "Orçamento"
                ui.notification_show(
                    f"✅ {tipo_texto} #{numero_venda} finalizada com sucesso!\n"
                    f"📥 Clique no botão para baixar a imagem.",
                    type="message", 
                    duration=8
                )

            except Exception as e:
                # Se der erro na geração da imagem, notifique e pare o processo
                print(f"\n❌ ERRO AO GERAR A IMAGEM DA VENDA:")
                print(f"   Tipo: {type(e).__name__}")
                print(f"   Mensagem: {str(e)}")
                import traceback
                traceback.print_exc()
                ui.notification_show(
                    "❌ Erro grave ao gerar a imagem da venda. A venda foi salva, mas a imagem não pôde ser criada.", 
                    type="error", 
                    duration=10
                )
                print("="*60 + "\n")
                # Não ative o trigger aqui, pois a imagem não foi gerada!
            
        except Exception as e:
            print(f"❌ Erro em finalizar_venda: {e}")
            import traceback
            traceback.print_exc()
            ui.notification_show(f"❌ Erro: {str(e)}", type="error")
    
    @reactive.Effect
    @reactive.event(input.btn_converter_orcamento)
    def converter_orcamento():
        try:
            if not input.orcamento_id():
                ui.notification_show("⚠️ Selecione um orçamento!", type="warning")
                return
            
            if not supabase:
                ui.notification_show("❌ Supabase não configurado", type="error")
                return
            
            orcamento_id = input.orcamento_id()
            result = supabase.table('vendas').select('*').eq('id', orcamento_id).execute()
            
            if not result.data:
                ui.notification_show("❌ Orçamento não encontrado!", type="error")
                return
            
            orcamento = result.data[0]
            
            if orcamento['tipo'] == 'venda':
                ui.notification_show("⚠️ Este orçamento já foi convertido em venda!", type="warning")
                return
            
            update_data = {
                "tipo": "venda",
                "status": "concluido"
            }
            
            supabase.table('vendas').update(update_data).eq('id', orcamento_id).execute()
            ui.notification_show(f"✅ Orçamento {orcamento['numero_venda']} convertido em venda!", 
                               type="message", duration=5)
            
        except Exception as e:
            ui.notification_show(f"❌ Erro: {str(e)}", type="error")

    
    # Tabelas
    @output
    @render.data_frame
    def tabela_usuarios():
        vendedores_trigger()
        try:
            if not supabase: return pd.DataFrame({"Mensagem": ["Supabase não configurado"]})
            result = supabase.table('usuarios').select('nome, email, tipo_usuario, ativo').execute()
            if not result.data: return pd.DataFrame({"Mensagem": ["Nenhum usuário"]})
            df = pd.DataFrame(result.data)
            df['tipo_usuario'] = df['tipo_usuario'].str.title()
            df['ativo'] = df['ativo'].apply(lambda x: '✅' if x else '❌')
            df.columns = ['Nome', 'Email', 'Tipo', 'Status']
            return df
        except: return pd.DataFrame({"Erro": ["Erro ao carregar"]})
    
    @output
    @render.data_frame
    def tabela_clinicas():
        clinicas_trigger() 
        
        try:
            if not supabase: return pd.DataFrame({"Mensagem": ["Supabase não configurado"]})
            result = supabase.table('clinicas').select('razao_social, nome_fantasia, telefone, ativo').execute()
            if not result.data: return pd.DataFrame({"Mensagem": ["Nenhuma clínica"]})
            df = pd.DataFrame(result.data)
            df['nome_fantasia'] = df['nome_fantasia'].fillna('-')
            df['telefone'] = df['telefone'].fillna('-')
            df['ativo'] = df['ativo'].apply(lambda x: '✅' if x else '❌')
            df.columns = ['Razão Social', 'Nome Fantasia', 'Telefone', 'Status']
            return df
        except: return pd.DataFrame({"Erro": ["Erro ao carregar"]})
    
    @output
    @render.data_frame
    def tabela_clientes():
        clientes_trigger()
        
        try:
            if not supabase: return pd.DataFrame({"Mensagem": ["Supabase não configurado"]})
            result = supabase.table('clientes').select('nome_completo, cpf, telefone, ativo').execute()
            if not result.data: return pd.DataFrame({"Mensagem": ["Nenhum cliente"]})
            df = pd.DataFrame(result.data)
            df['cpf'] = df['cpf'].apply(formatar_cpf)
            df['telefone'] = df['telefone'].fillna('-')
            df['ativo'] = df['ativo'].apply(lambda x: '✅' if x else '❌')
            df.columns = ['Nome', 'CPF', 'Telefone', 'Status']
            return df
        except: return pd.DataFrame({"Erro": ["Erro ao carregar"]})
    
    @output
    @render.data_frame
    def tabela_vendas():
        try:
            if not supabase: return pd.DataFrame({"Mensagem": ["Supabase não configurado"]})
            result = supabase.table('vendas').select('numero_venda, tipo, valor_total, status, criado_em').limit(50).order('criado_em', desc=True).execute()
            if not result.data: return pd.DataFrame({"Mensagem": ["Nenhuma venda"]})
            df = pd.DataFrame(result.data)
            df['valor_total'] = df['valor_total'].apply(formatar_moeda)
            df['tipo'] = df['tipo'].str.title()
            df['criado_em'] = pd.to_datetime(df['criado_em']).dt.strftime('%d/%m/%Y %H:%M')
            df.columns = ['Número', 'Tipo', 'Valor', 'Status', 'Data']
            return df
        except: return pd.DataFrame({"Erro": ["Erro ao carregar"]})
    
    @output
    @render.data_frame
    def tabela_minhas_vendas():
        try:
            user = user_data()
            if not user or not supabase: return pd.DataFrame({"Mensagem": ["Nenhuma venda"]})
            result = supabase.table('vendas').select('numero_venda, tipo, valor_total, status, criado_em').eq('vendedor_id', user['id']).order('criado_em', desc=True).execute()
            if not result.data: return pd.DataFrame({"Mensagem": ["Nenhuma venda"]})
            df = pd.DataFrame(result.data)
            df['valor_total'] = df['valor_total'].apply(formatar_moeda)
            df['tipo'] = df['tipo'].str.title()
            df['criado_em'] = pd.to_datetime(df['criado_em']).dt.strftime('%d/%m/%Y %H:%M')
            df.columns = ['Número', 'Tipo', 'Valor', 'Status', 'Data']
            return df
        except: return pd.DataFrame({"Erro": ["Erro ao carregar"]})
    
    
    @output
    @render.ui
    def tabela_procedimentos():
        """Tabela de procedimentos com botões de editar e excluir"""
        procedimentos_trigger()
        
        try:
            user = user_data()
            if not user or not supabase:
                return ui.div(
                    {"style": "text-align: center; padding: 3rem; color: #94a3b8;"},
                    ui.h5("📭 Nenhum procedimento")
                )
            
            clinica_result = supabase.table('clinicas').select('id').eq('usuario_id', user['id']).execute()
            if not clinica_result.data:
                return ui.div(
                    {"style": "text-align: center; padding: 3rem; color: #94a3b8;"},
                    ui.h5("❌ Clínica não encontrada")
                )
            
            result = supabase.table('procedimentos').select(
                '*'
            ).eq('clinica_id', clinica_result.data[0]['id']).order('nome').execute()
            
            if not result.data:
                return ui.div(
                    {"style": "text-align: center; padding: 3rem; color: #94a3b8;"},
                    ui.h5("📭 Nenhum procedimento cadastrado"),
                    ui.p("Os procedimentos que você cadastrar aparecerão aqui")
                )
            
            cards = []
            for proc in result.data:
                ativo = proc.get('ativo', True)
                cor_border = "#10b981" if ativo else "#ef4444"
                
                card = ui.div(
                    {"class": "card-custom", "style": f"margin-bottom: 1rem; border-left: 4px solid {cor_border};"},
                    ui.row(
                        ui.column(7,
                            ui.h6(proc.get('nome', 'N/A'), style="margin: 0 0 0.5rem 0;"),
                            ui.p(f"💰 {formatar_moeda(proc.get('preco', 0))}", 
                                 style="margin: 0.25rem 0; font-size: 1rem; font-weight: 700; color: #1DD1A1;"),
                            ui.p(f"📋 Descrição: {proc.get('descricao', '-')[:100]}", 
                                 style="margin: 0.25rem 0; font-size: 0.85rem; color: #546E7A;") if proc.get('descricao') else None
                        ),
                        ui.column(5,
                            ui.div(
                                {"style": "text-align: right;"},
                                ui.tags.button(
                                    "✏️ Editar Preço",
                                    class_="btn btn-primary w-100 mb-2",
                                    onclick=f"Shiny.setInputValue('editar_proc_id', '{proc['id']}', {{priority: 'event'}})",
                                    style="font-weight: 600; padding: 0.5rem; font-size: 0.9rem;"
                                ),
                                ui.tags.button(
                                    "🔄 Ativar" if not ativo else "⏸️ Desativar",
                                    class_=f"btn {'btn-success' if not ativo else 'btn-warning'} w-100 mb-2",
                                    onclick=f"Shiny.setInputValue('toggle_proc_id', '{proc['id']}', {{priority: 'event'}})",
                                    style="font-weight: 600; padding: 0.5rem; font-size: 0.9rem;"
                                ),

                            )
                        )
                    )
                )
                cards.append(card)
            
            return ui.div(*cards)
            
        except Exception as e:
            print(f"Erro tabela_procedimentos: {e}")
            import traceback
            traceback.print_exc()
            return ui.div(
                {"class": "alert alert-danger"},
                ui.h5("❌ Erro ao carregar procedimentos"),
                ui.p(str(e))
            )

    @reactive.Effect
    def _monitor_editar_procedimento():
        """Abre modal para editar preço do procedimento"""
        try:
            proc_id = None
            try:
                proc_id = input.editar_proc_id()
            except:
                return
            
            if not proc_id or not supabase:
                return
            
            print(f"\n{'='*60}")
            print(f"✏️ EDITAR PROCEDIMENTO - DEBUG")
            print(f"{'='*60}")
            print(f"Procedimento ID: {proc_id}")
            
            # Busca dados do procedimento
            result = supabase.table('procedimentos').select('*').eq('id', proc_id).execute()
            
            if not result.data:
                ui.notification_show("❌ Procedimento não encontrado!", type="error")
                return
            
            proc = result.data[0]
            preco_atual = float(proc.get('preco', 0))
            
            print(f"📋 Nome: {proc.get('nome')}")
            print(f"💰 Preço atual: {formatar_moeda(preco_atual)}")
            
            # Remove modal anterior se existir
            ui.remove_ui(selector=f"#edit_proc_modal_{proc_id}")
            
            # Cria modal de edição CORRIGIDO
            modal_html = f'''
            <div id="edit_proc_modal_{proc_id}" style="
                position: fixed; top: 0; left: 0; width: 100%; height: 100%; 
                background: rgba(0,0,0,0.8); z-index: 9999; 
                display: flex; align-items: center; justify-content: center;
            ">
                <div style="
                    background: white; border-radius: 1rem; padding: 2rem; 
                    max-width: 500px; width: 90%;
                " onclick="event.stopPropagation()">
                    <h3 style="color: #1DD1A1; margin-bottom: 1.5rem;">✏️ Editar Procedimento</h3>
                    
                    <div style="background: #f8fafc; padding: 1rem; border-radius: 0.5rem; margin-bottom: 1.5rem;">
                        <h5 style="margin: 0 0 0.5rem 0; color: #2D3748;">📋 {proc.get('nome', 'N/A')}</h5>
                        <p style="margin: 0; color: #546E7A; font-size: 0.9rem;">Preço atual: {formatar_moeda(preco_atual)}</p>
                    </div>
                    
                    <form id="form_edit_proc_{proc_id}">
                        <div style="margin-bottom: 1.5rem;">
                            <label style="display: block; font-weight: 600; margin-bottom: 0.5rem;">💰 Novo Preço (R$)</label>
                            <input type="number" id="edit_preco_{proc_id}" 
                                   value="{preco_atual}" 
                                   min="0" step="0.01"
                                   style="width: 100%; padding: 0.75rem; border: 2px solid #e2e8f0; border-radius: 0.5rem; font-size: 1.1rem;"
                                   placeholder="0,00">
                        </div>
                        
                        <div style="display: flex; gap: 1rem; margin-top: 2rem;">
                            <button type="button" onclick="
                                const novoPreco = parseFloat(document.getElementById('edit_preco_{proc_id}').value);
                                
                                if (!novoPreco || novoPreco <= 0) {{
                                    alert('⚠️ Digite um preço válido!');
                                    return;
                                }}
                                
                                const data = {{
                                    id: '{proc_id}',
                                    preco: novoPreco
                                }};
                                
                                Shiny.setInputValue('salvar_edicao_proc', JSON.stringify(data), {{priority: 'event'}});
                                document.getElementById('edit_proc_modal_{proc_id}').remove();
                            " style="
                                flex: 1; background: #10b981; color: white; border: none; 
                                padding: 0.75rem; border-radius: 0.5rem; font-weight: 600; cursor: pointer;
                            ">💾 Salvar</button>
                            
                            <button type="button" onclick="document.getElementById('edit_proc_modal_{proc_id}').remove()" 
                                style="
                                    flex: 1; background: #ef4444; color: white; border: none; 
                                    padding: 0.75rem; border-radius: 0.5rem; font-weight: 600; cursor: pointer;
                                ">❌ Cancelar</button>
                        </div>
                    </form>
                </div>
            </div>
            '''
            
            ui.insert_ui(
                selector="body",
                where="beforeEnd",
                ui=ui.HTML(modal_html)
            )
            
            print(f"✅ Modal de edição criado!")
            print(f"{'='*60}\n")
            
        except Exception as e:
            print(f"❌ Erro _monitor_editar_procedimento: {e}")
            import traceback
            traceback.print_exc()
            ui.notification_show(f"❌ Erro: {str(e)}", type="error")


    @reactive.Effect
    @reactive.event(input.salvar_edicao_proc)
    def _monitor_salvar_edicao_proc():
        """Salva a edição do preço do procedimento"""
        try:
            dados_json = None
            try:
                dados_json = input.salvar_edicao_proc()
            except:
                return
            
            if not dados_json or not supabase:
                return
            
            import json
            dados = json.loads(dados_json)
            
            proc_id = dados.get('id')
            novo_preco = float(dados.get('preco'))
            
            print(f"\n{'='*60}")
            print(f"💾 SALVANDO EDIÇÃO - DEBUG")
            print(f"{'='*60}")
            print(f"Procedimento ID: {proc_id}")
            print(f"Novo preço: {formatar_moeda(novo_preco)}")
            
            # Busca nome do procedimento
            proc_result = supabase.table('procedimentos').select('nome').eq('id', proc_id).execute()
            proc_nome = proc_result.data[0].get('nome', 'N/A') if proc_result.data else 'N/A'
            
            # Atualiza no banco
            update_result = supabase.table('procedimentos').update({
                'preco': novo_preco
            }).eq('id', proc_id).execute()
            
            if not update_result.data:
                ui.notification_show("❌ Erro ao atualizar preço!", type="error")
                return
            
            # ✅ FORÇA ATUALIZAÇÃO INSTANTÂNEA DA TABELA
            procedimentos_trigger.set(procedimentos_trigger() + 1)
            
            print(f"✅ Preço atualizado com sucesso!")
            print(f"{'='*60}\n")
            
            ui.notification_show(
                f"✅ Preço atualizado com sucesso!\n"
                f"📋 {proc_nome}\n"
                f"💰 Novo preço: {formatar_moeda(novo_preco)}",
                type="message",
                duration=5
            )
            
        except Exception as e:
            print(f"❌ Erro _monitor_salvar_edicao_proc: {e}")
            import traceback
            traceback.print_exc()
            ui.notification_show(f"❌ Erro ao salvar: {str(e)}", type="error")

    @reactive.Effect
    @reactive.event(input.toggle_proc_id) # <-- ADICIONADO
    def _monitor_toggle_procedimento():
        """Ativa ou desativa um procedimento"""
        try:
            proc_id = None
            try:
                proc_id = input.toggle_proc_id() # Agora apenas lê o valor
            except:
                return
            
            if not proc_id or not supabase:
                return
            
            print(f"\n{'='*60}")
            print(f"🔄 TOGGLE PROCEDIMENTO - DEBUG")
            print(f"{'='*60}")
            print(f"Procedimento ID: {proc_id}")
            
            # Busca status atual
            result = supabase.table('procedimentos').select('ativo, nome').eq('id', proc_id).execute()
            
            if not result.data:
                return
            
            proc = result.data[0]
            novo_status = not proc.get('ativo', True)
            
            # Atualiza
            supabase.table('procedimentos').update({
                'ativo': novo_status
            }).eq('id', proc_id).execute()
            
            # Força atualização da tabela
            procedimentos_trigger.set(procedimentos_trigger() + 1)
            
            print(f"✅ Status alterado: {'Ativo' if novo_status else 'Inativo'}")
            print(f"{'='*60}\n")
            
            ui.notification_show(
                f"{'✅ Ativado' if novo_status else '⏸️ Desativado'}: {proc['nome']}",
                type="message",
                duration=3
            )
            
        except Exception as e:
            print(f"❌ Erro _monitor_toggle_procedimento: {e}")
            ui.notification_show(f"❌ Erro: {str(e)}", type="error")


  
  
    # Gráficos
    @output
    @render.plot
    def grafico_vendas_periodo():
        try:
            if not supabase:
                import matplotlib.pyplot as plt
                fig, ax = plt.subplots()
                ax.text(0.5, 0.5, 'Dados não disponíveis', ha='center', va='center')
                return fig
            
            result = supabase.table('vendas').select('criado_em, valor_total').eq('tipo', 'venda').execute()
            if not result.data:
                import matplotlib.pyplot as plt
                fig, ax = plt.subplots()
                ax.text(0.5, 0.5, 'Nenhuma venda registrada', ha='center', va='center')
                return fig
            
            df = pd.DataFrame(result.data)
            df['criado_em'] = pd.to_datetime(df['criado_em'])
            df['data'] = df['criado_em'].dt.date
            vendas_por_dia = df.groupby('data')['valor_total'].sum().reset_index()
            
            import matplotlib.pyplot as plt
            fig, ax = plt.subplots(figsize=(10, 5))
            ax.plot(vendas_por_dia['data'], vendas_por_dia['valor_total'], marker='o', linewidth=2, color='#1DD1A1')
            ax.set_xlabel('Data')
            ax.set_ylabel('Valor (R$)')
            ax.set_title('Vendas por Período')
            ax.grid(True, alpha=0.3)
            plt.xticks(rotation=45)
            plt.tight_layout()
            return fig
        except:
            import matplotlib.pyplot as plt
            fig, ax = plt.subplots()
            ax.text(0.5, 0.5, 'Erro ao gerar gráfico', ha='center', va='center')
            return fig
    
    @output
    @render.plot
    def grafico_top_procedimentos():
        try:
            if not supabase:
                import matplotlib.pyplot as plt
                fig, ax = plt.subplots()
                ax.text(0.5, 0.5, 'Dados não disponíveis', ha='center', va='center')
                return fig
            
            result = supabase.table('itens_venda').select('nome_procedimento, quantidade').execute()
            if not result.data:
                import matplotlib.pyplot as plt
                fig, ax = plt.subplots()
                ax.text(0.5, 0.5, 'Nenhum item vendido', ha='center', va='center')
                return fig
            
            df = pd.DataFrame(result.data)
            top = df.groupby('nome_procedimento')['quantidade'].sum().sort_values(ascending=False).head(10)
            
            import matplotlib.pyplot as plt
            fig, ax = plt.subplots(figsize=(10, 5))
            ax.barh(range(len(top)), top.values, color='#0D9488')
            ax.set_yticks(range(len(top)))
            ax.set_yticklabels(top.index)
            ax.set_xlabel('Quantidade Vendida')
            ax.set_title('Top 10 Procedimentos Mais Vendidos')
            ax.grid(True, alpha=0.3, axis='x')
            plt.tight_layout()
            return fig
        except:
            import matplotlib.pyplot as plt
            fig, ax = plt.subplots()
            ax.text(0.5, 0.5, 'Erro ao gerar gráfico', ha='center', va='center')
            return fig
    
    # Downloads
    @output
    @render.ui
    def btn_download_contrato_wrapper():
        contrato = ultimo_contrato()
        if not contrato:
            return ui.div()
        
        return ui.div(
            {"class": "mt-3 p-3", "style": "background: #dcfce7; border-radius: 0.5rem; border: 2px solid #16a34a;"},
            ui.row(
                ui.column(8,
                    ui.h5("✅ Contrato Pronto!", style="color: #16a34a; margin: 0;"),
                    ui.p(f"Clínica: {contrato['clinica']}", style="margin: 0.5rem 0 0 0; font-size: 0.9rem;"),
                    ui.p(f"Login: {contrato['usuario']} | Senha: {contrato['senha']}", 
                         style="margin: 0.25rem 0 0 0; font-size: 0.85rem; font-family: monospace; color: #15803d;")
                ),
                ui.column(4,
                    ui.download_button("btn_download_contrato", "📥 Baixar Contrato PDF",
                                      class_="btn btn-success w-100 mt-2")
                )
            )
        )
    

    @render.download(
        filename=lambda: ultima_venda_pdf().get('filename', 'venda.pdf') if ultima_venda_pdf() else "venda.pdf"
    )
    def btn_download_venda_pdf():
        """Baixa o PDF da venda"""
        print("\n" + "="*60)
        print("📥 INICIANDO DOWNLOAD DO PDF")
        print("="*60)
        
        try:
            venda_pdf = ultima_venda_pdf()
            print(f"1️⃣ Verificando venda_pdf...")
            print(f"   - Valor: {venda_pdf}")
            
            if not venda_pdf:
                print("❌ ERRO: Nenhum PDF disponível!")
                print("="*60 + "\n")
                yield b"Erro: Nenhum PDF disponivel"
                return

            if 'pdf' not in venda_pdf:
                print("❌ ERRO: Chave 'pdf' não encontrada!")
                print("="*60 + "\n")
                yield b"Erro: PDF nao encontrado"
                return

            pdf_bytes = venda_pdf['pdf']
            print(f"2️⃣ PDF encontrado!")
            print(f"   - Tipo: {type(pdf_bytes)}")
            print(f"   - Tamanho: {len(pdf_bytes) if isinstance(pdf_bytes, bytes) else 'N/A'} bytes")
            
            if not isinstance(pdf_bytes, bytes):
                print(f"❌ ERRO: PDF não é bytes! É {type(pdf_bytes)}")
                print("="*60 + "\n")
                yield b"Erro: Formato invalido"
                return

            if len(pdf_bytes) == 0:
                print("❌ ERRO: PDF vazio!")
                print("="*60 + "\n")
                yield b"Erro: PDF vazio"
                return
            
            print(f"3️⃣ Enviando PDF para download...")
            print(f"   - Filename: {venda_pdf.get('filename')}")
            print(f"   - Número da venda: {venda_pdf.get('numero_venda')}")
            print("="*60 + "\n")
            
            yield pdf_bytes
            
        except Exception as e:
            print(f"\n❌ ERRO CRÍTICO no download:")
            print(f"   Tipo: {type(e).__name__}")
            print(f"   Mensagem: {str(e)}")
            import traceback
            traceback.print_exc()
            print("="*60 + "\n")
            yield b"Erro ao baixar PDF"
            
            
    @render.download(
        filename=lambda: ultimo_contrato()['filename'] if ultimo_contrato() else "contrato.pdf"
    )
    def btn_download_contrato():
        """Baixa o contrato gerado no cadastro"""
        try:
            contrato = ultimo_contrato()
            if not contrato or 'pdf' not in contrato:
                from reportlab.pdfgen import canvas
                from reportlab.lib.pagesizes import A4
                buffer = BytesIO()
                c = canvas.Canvas(buffer, pagesize=A4)
                c.setFont("Helvetica", 12)
                c.drawString(100, 400, "Nenhum contrato disponivel")
                c.drawString(100, 380, "Cadastre uma clinica primeiro")
                c.showPage()
                c.save()
                buffer.seek(0)
                yield buffer.getvalue() # MUDANÇA AQUI
                return

            pdf_bytes = contrato['pdf']
            print(f"✅ Retornando PDF do contrato: {len(pdf_bytes)} bytes")
            yield pdf_bytes # MUDANÇA AQUI
            
        except Exception as e:
            print(f"❌ Erro no download: {e}")
            import traceback
            traceback.print_exc()
            
            from reportlab.pdfgen import canvas
            from reportlab.lib.pagesizes import A4
            buffer = BytesIO()
            c = canvas.Canvas(buffer, pagesize=A4)
            c.setFont("Helvetica", 12)
            c.drawString(100, 400, "Erro ao gerar contrato")
            c.showPage()
            c.save()
            buffer.seek(0)
            yield buffer.getvalue() # MUDANÇA AQUI


    # ========== BUSCAR VENDA PARA ATENDIMENTO ==========
    @reactive.Effect
    @reactive.event(input.btn_buscar_venda, atendimento_trigger)
    def buscar_venda_atendimento():
        try:
            codigo = input.codigo_venda()
            
            if not codigo or not supabase:
                ui.notification_show("⚠️ Digite o código da venda!", type="warning")
                return
            
            # Remove espaços e converte para maiúsculas
            codigo_limpo = codigo.strip().upper()
            
            print(f"\n{'='*60}")
            print(f"🔍 BUSCANDO VENDA")
            print(f"Código digitado: '{codigo}'")
            print(f"Código limpo: '{codigo_limpo}'")
            
            # Query corrigida: sem tabela beneficiarios
            result = supabase.table('vendas').select(
                '*, clientes(*), itens_venda(*)'
            ).ilike('numero_venda', codigo_limpo).execute()
            
            print(f"Resultado: {len(result.data) if result.data else 0} venda(s) encontrada(s)")
            
            if result.data:
                venda = result.data[0]
                print(f"Dados da venda: {venda.keys()}")
                
                # Verifica se tem beneficiário
                if venda.get('beneficiario_nome'):
                    print(f"🎁 PRESENTE")
                    print(f"   Comprador: {venda.get('clientes', {}).get('nome_completo', 'N/A')}")
                    print(f"   Beneficiário: {venda.get('beneficiario_nome')} (CPF: {venda.get('beneficiario_cpf', 'N/A')})")
                else:
                    cliente = venda.get('clientes')
                    print(f"👤 COMPRA PRÓPRIA - Cliente: {cliente.get('nome_completo', 'N/A') if cliente else 'N/A'}")
            
            print(f"{'='*60}\n")
            
            if not result.data:
                venda_atual.set(None)
                ui.notification_show(f"❌ Venda {codigo_limpo} não encontrada!", type="error")
                return
            
            venda = result.data[0]
            
            # Verifica se é da clínica atual
            user = user_data()
            clinica_result = supabase.table('clinicas').select('id').eq('usuario_id', user['id']).execute()
            
            if not clinica_result.data:
                ui.notification_show("❌ Erro ao identificar clínica!", type="error")
                return
            
            clinica_id = clinica_result.data[0]['id']
            
            if venda['clinica_id'] != clinica_id:
                ui.notification_show("⚠️ Esta venda não é desta clínica!", type="warning")
                return
            
            venda_atual.set(venda)
            itens_atendimento.set(venda.get('itens_venda', []))
            
            # ✅ CORREÇÃO PRINCIPAL: Mostra beneficiário no atendimento
            cliente = venda.get('clientes', {})
            
            if venda.get('beneficiario_nome'):
                # É PRESENTE: mostra dados do beneficiário
                nome_atendimento = venda.get('beneficiario_nome')
                cpf_atendimento = venda.get('beneficiario_cpf', 'Não informado')
                tipo = "🎁 Presente"
                info_adicional = f"Comprado por: {cliente.get('nome_completo', 'N/A')}"
            else:
                # COMPRA PRÓPRIA: mostra dados do cliente
                nome_atendimento = cliente.get('nome_completo', 'N/A')
                cpf_atendimento = cliente.get('cpf', 'Não informado')
                tipo = "👤 Uso Próprio"
                info_adicional = ""
            
            status = "✅ APTO PARA ATENDIMENTO" if venda.get('pagamento_confirmado') else "⏳ AGUARDANDO CONFIRMAÇÃO DE PAGAMENTO"
            
            # Monta mensagem completa
            mensagem = f"{tipo}: {nome_atendimento}"
            if info_adicional:
                mensagem += f"\n{info_adicional}"
            mensagem += f"\nStatus: {status}"
            
            ui.notification_show(
                mensagem, 
                type="message",
                duration=8
            )
            
        except Exception as e:
            print(f"Erro buscar_venda_atendimento: {e}")
            import traceback
            traceback.print_exc()
            ui.notification_show(f"❌ Erro: {str(e)}", type="error")

# ========== RENDERIZAR RESULTADO DA BUSCA (VERSÃO SIMPLIFICADA) ==========
    @output
    @render.ui
    def resultado_busca_venda():
        venda = venda_atual()
        
        if not venda:
            return ui.div(
                {"style": "text-align: center; padding: 3rem; color: #94a3b8;"},
                ui.h5("🔍 Digite o código da venda acima"),
                ui.p("O sistema verificará se o cliente está apto ao atendimento")
            )
        
        # ========== INÍCIO DA LÓGICA REVISADA ==========
        cliente_comprador = venda.get('clientes', {})
        itens = itens_atendimento()

        if venda.get('beneficiario_nome'):
            # É PRESENTE/TERCEIRO - Mostra SOMENTE nome e CPF do beneficiário
            nome_atendimento = venda.get('beneficiario_nome')
            cpf_atendimento = venda.get('beneficiario_cpf', 'Não informado')
            
            # --- NÃO MOSTRAR DADOS DO COMPRADOR OU "N/A" ---
            telefone_atendimento = None # Não exibir
            email_atendimento = None # Não exibir
            foto_url = None # Não temos foto do beneficiário
            
        else:
            # COMPRA PRÓPRIA - Mostra dados completos do cliente comprador
            nome_atendimento = cliente_comprador.get('nome_completo', 'Não informado')
            cpf_atendimento = cliente_comprador.get('cpf', 'Não informado')
            telefone_atendimento = cliente_comprador.get('telefone', '-')
            email_atendimento = cliente_comprador.get('email', '-')
            foto_url = cliente_comprador.get('foto_url', '')
        # ========== FIM DA LÓGICA REVISADA ==========

        # Status de pagamento
        apto = venda.get('pagamento_confirmado', False)
        status_cor = "#10b981" if apto else "#f59e0b"
        status_texto = "✅ APTO PARA ATENDIMENTO" if apto else "⏳ AGUARDANDO CONFIRMAÇÃO DE PAGAMENTO"
        status_icone = "✅" if apto else "⏳"
        
        # Card do cliente/beneficiário
        foto_html = f'<img src="{foto_url}" style="width: 120px; height: 120px; border-radius: 50%; object-fit: cover; border: 4px solid white; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">' if foto_url else '<div style="width: 120px; height: 120px; border-radius: 50%; background: #e2e8f0; display: flex; align-items: center; justify-content: center; font-size: 3rem;">👤</div>'
        
        return ui.div(
            # Status Card
            ui.div(
                {"class": "card-custom", "style": f"background: {status_cor}; color: white; text-align: center; margin-bottom: 1.5rem;"},
                ui.h3(f"{status_icone} {status_texto}", style="margin: 0;")
            ),
            
            # Dados da Pessoa (Cliente ou Beneficiário)
            ui.div(
                {"class": "card-custom"},
                
                # --- REMOVIDO: Badge "TIPO PESSOA" ---
                
                ui.h4("👤 Dados para Atendimento", style="margin-bottom: 1.5rem;"),
                ui.row(
                    ui.column(3,
                        ui.HTML(f'<div style="text-align: center;">{foto_html}</div>')
                    ),
                    ui.column(9,
                        ui.h5(nome_atendimento, 
                              style="margin: 0 0 1rem 0; color: #2D3748;"),
                        
                        # --- REMOVIDO: Bloco "Presente de:" ---
                        
                        ui.row(
                            ui.column(6,
                                ui.p(f"📄 CPF: {formatar_cpf(cpf_atendimento)}", 
                                     style="margin: 0.5rem 0;"),
                                
                                # --- LÓGICA CONDICIONAL ADICIONADA ---
                                # Só mostra telefone se a variável não for None
                                ui.p(f"📱 Telefone: {telefone_atendimento}", 
                                     style="margin: 0.5rem 0;") if telefone_atendimento else None
                            ),
                            ui.column(6,
                                ui.p(f"🆔 Código: {venda.get('numero_venda', '-')}", 
                                     style="margin: 0.5rem 0;"),
                                
                                # --- LÓGICA CONDICIONAL ADICIONADA ---
                                # Só mostra email se a variável não for None
                                ui.p(f"📧 Email: {email_atendimento}", 
                                     style="margin: 0.5rem 0;") if email_atendimento else None
                            )
                        )
                    )
                )
            ),
            
            # Procedimentos (o restante da função permanece igual)
            ui.div(
                {"class": "card-custom"},
                ui.h4("🔬 Procedimentos Adquiridos", style="margin-bottom: 1.5rem;"),
                ui.output_ui("lista_procedimentos_atendimento"),
                ui.div(
                    {"style": "margin-top: 2rem; text-align: right;"},
                    ui.input_action_button("btn_registrar_atendimento", 
                                          "✅ Registrar Atendimento", 
                                          class_="btn-primary",
                                          style="padding: 1rem 3rem; font-size: 1.1rem;")
                ) if apto else ui.div(
                    {"style": "background: #fef3c7; border-left: 4px solid #f59e0b; padding: 1rem; margin-top: 1rem;"},
                    ui.p("⏳ Aguardando confirmação de pagamento pelo superusuário", 
                         style="margin: 0; color: #92400e;")
                )
            )
        )
        
# ============================================================
# RENDERIZAÇÃO DA INTERFACE DE ATENDIMENTO
# ============================================================

    @output
    @render.ui
    def info_paciente_atendimento():
        """Mostra as informações da pessoa que será atendida"""
        venda = venda_atual()
        
        if not venda:
            return ui.div(
                {"class": "alert alert-info"},
                ui.markdown("ℹ️ Digite o código da venda acima para buscar o atendimento.")
            )
        
        cliente = venda.get('clientes', {})
        
        # ✅ DECISÃO: Beneficiário ou Cliente?
        if venda.get('beneficiario_nome'):
            # É PRESENTE - Mostra beneficiário
            nome = venda.get('beneficiario_nome', 'Não informado')
            cpf = venda.get('beneficiario_cpf', 'Não informado')
            tipo_badge = ui.tags.span(
                "🎁 PRESENTE",
                class_="badge bg-success me-2"
            )
            info_comprador = ui.div(
                {"class": "alert alert-info mt-2 mb-0"},
                ui.markdown(f"**Comprado por:** {cliente.get('nome_completo', 'N/A')}")
            )
        else:
            # COMPRA PRÓPRIA - Mostra cliente
            nome = cliente.get('nome_completo', 'Não informado')
            cpf = cliente.get('cpf', 'Não informado')
            tipo_badge = ui.tags.span(
                "👤 USO PRÓPRIO",
                class_="badge bg-primary me-2"
            )
            info_comprador = None
        
        # Status do pagamento
        if venda.get('pagamento_confirmado'):
            status_badge = ui.tags.span("✅ APTO", class_="badge bg-success")
        else:
            status_badge = ui.tags.span("⏳ AGUARDANDO", class_="badge bg-warning text-dark")
        
        return ui.div(
            ui.card(
                ui.card_header(
                    ui.h5("👤 Informações do Paciente", class_="mb-0")
                ),
                ui.card_body(
                    ui.div(
                        tipo_badge,
                        status_badge
                    ),
                    ui.hr(),
                    ui.row(
                        ui.column(6,
                            ui.p(ui.strong("Nome:"), class_="mb-1"),
                            ui.p(nome, class_="mb-3")
                        ),
                        ui.column(6,
                            ui.p(ui.strong("CPF:"), class_="mb-1"),
                            ui.p(cpf, class_="mb-3")
                        )
                    ),
                    ui.row(
                        ui.column(6,
                            ui.p(ui.strong("Venda:"), class_="mb-1"),
                            ui.p(venda.get('numero_venda', 'N/A'), class_="mb-3")
                        ),
                        ui.column(6,
                            ui.p(ui.strong("Valor Total:"), class_="mb-1"),
                            ui.p(f"R$ {float(venda.get('valor_total', 0)):.2f}", class_="mb-3")
                        )
                    ),
                    info_comprador if info_comprador else ui.div()
                )
            )
        )


    # ========== LISTA DE PROCEDIMENTOS COM CHECKBOXES ==========
    @output
    @render.ui
    def lista_procedimentos_atendimento():
        itens = itens_atendimento()
        
        if not itens:
            return ui.p("Nenhum procedimento", style="color: #94a3b8;")
        
        # --- NOVO: Agrupa por pacote ---
        itens_por_pacote = {}
        itens_individuais = []
        
        for item in itens:
            pacote_id = item.get('pacote_id')
            if pacote_id:
                if pacote_id not in itens_por_pacote:
                    # Busca nome do pacote
                    pacote_nome = "Pacote"
                    try:
                        pac_res = supabase.table('pacotes').select('nome').eq('id', pacote_id).maybe_single().execute()
                        if pac_res.data:
                            pacote_nome = pac_res.data['nome']
                    except: pass
                    itens_por_pacote[pacote_id] = {
                        'nome': pacote_nome,
                        'itens': []
                    }
                itens_por_pacote[pacote_id]['itens'].append(item)
            else:
                itens_individuais.append(item)
        
        cards = []
        
        # --- 1. Renderiza Pacotes ---
        for pacote_id, pacote_info in itens_por_pacote.items():
            pacote_cards_html = []
            todos_atendidos_pacote = True
            
            for i, item in enumerate(pacote_info['itens']):
                # (Precisa de um índice único para o checkbox)
                item_idx_global = itens.index(item) 
                atendido = item.get('atendido', False)
                if not atendido:
                    todos_atendidos_pacote = False
                
                # Checkbox
                if atendido:
                    checkbox_html = ui.div(
                        {"style": "text-align: center; font-size: 1.5rem; color: #10b981;"},
                        "✅"
                    )
                else:
                    checkbox_html = ui.div(
                        {"style": "text-align: center;"},
                        ui.input_checkbox(f"item_atend_{item_idx_global}", "", value=False)
                    )

                pacote_cards_html.append(
                    ui.div(
                        {"style": f"background: {'#f1f5f9' if atendido else '#ffffff'}; border: 1px solid {'#10b981' if atendido else '#e2e8f0'}; border-radius: 0.5rem; padding: 0.75rem; margin-bottom: 0.5rem;"},
                        ui.row(
                            {"style": "align-items: center;"},
                            ui.column(1, checkbox_html),
                            ui.column(8, ui.h6(item.get('nome_procedimento', 'N/A'), style="margin: 0;")),
                            ui.column(3, ui.p("✅ Atendido" if atendido else "⏳ Pendente", 
                                             style=f"margin: 0; text-align: right; font-size: 0.85rem; color: {'#10b981' if atendido else '#f59e0b'};"))
                        )
                    )
                )
            
            # Card do Pacote
            cards.append(
                ui.div(
                    {"class": "card-custom", "style": f"margin-bottom: 1rem; background: #f0f9ff; border-left: 4px solid {'#10b981' if todos_atendidos_pacote else '#3b82f6'};"},
                    ui.h5(f"🎁 Pacote: {pacote_info['nome']}", style="color: #1e40af; margin-bottom: 1rem;"),
                    *pacote_cards_html
                )
            )

        # --- 2. Renderiza Itens Individuais ---
        for i, item in enumerate(itens_individuais):
            item_idx_global = itens.index(item)
            atendido = item.get('atendido', False)
            cor_card = "#f1f5f9" if atendido else "#ffffff"
            border_cor = "#10b981" if atendido else "#e2e8f0"
            
            if atendido:
                checkbox_html = ui.div(
                    {"style": "text-align: center; font-size: 2rem; color: #10b981;"},
                    "✅"
                )
            else:
                checkbox_html = ui.div(
                    {"style": "text-align: center;"},
                    ui.input_checkbox(f"item_atend_{item_idx_global}", "", value=False)
                )
            
            card = ui.div(
                {"style": f"background: {cor_card}; border: 2px solid {border_cor}; border-radius: 0.5rem; padding: 1rem; margin-bottom: 1rem;"},
                ui.row(
                    {"style": "align-items: center;"},
                    ui.column(1, checkbox_html),
                    ui.column(8,
                        ui.h6(f"🔬 {item.get('nome_procedimento', 'N/A')}", style="margin: 0 0 0.5rem 0;"),
                        ui.p(f"Quantidade: {item.get('quantidade', 1)}", style="margin: 0; color: #546E7A; font-size: 0.9rem;")
                    ),
                    ui.column(3,
                        ui.div(
                            {"style": "text-align: right;"},
                            ui.h6(formatar_moeda(item.get('preco_total', 0)), style="margin: 0; color: #1DD1A1;"),
                            ui.p("✅ Atendido" if atendido else "⏳ Pendente", 
                                 style=f"margin: 0.25rem 0 0 0; font-size: 0.85rem; color: {'#10b981' if atendido else '#f59e0b'};")
                        )
                    )
                )
            )
            cards.append(card)
        
        return ui.div(*cards)

    # ========== REGISTRAR ATENDIMENTO ==========
    @reactive.Effect
    @reactive.event(input.btn_registrar_atendimento)
    def registrar_atendimento():
        try:
            venda = venda_atual()
            if not venda or not supabase:
                return
            
            user = user_data()
            if not user:
                return
            
            itens = itens_atendimento()
            itens_para_atender = []
            
            # Verifica quais itens foram marcados
            for i, item in enumerate(itens):
                if item.get('atendido'):
                    continue  # Já foi atendido
                
                try:
                    marcado = input[f"item_atend_{i}"]()
                    if marcado:
                        itens_para_atender.append(item['id'])
                except:
                    pass
            
            if not itens_para_atender:
                ui.notification_show("⚠️ Selecione pelo menos um procedimento!", type="warning")
                return
            
            # Atualiza os itens no banco
            for item_id in itens_para_atender:
                supabase.table('itens_venda').update({
                    'atendido': True,
                    'data_atendimento': datetime.now().isoformat(),
                    'usuario_atendeu_id': user['id']
                }).eq('id', item_id).execute()
                
                # Notifica clínica que parcela 2 está disponível
                try:
                    venda = supabase.table('vendas').select('*, clinicas(*)').eq('id', venda_id).single().execute()
                    if venda.data:
                        clinica = venda.data.get('clinicas', {})
                        valor_parcela = venda.data['valor_total'] * 0.5
                        
                        mensagem = f"""
                ✅ *ATENDIMENTOS CONCLUÍDOS!*

                Parcela 2 disponível: R$ {valor_parcela:.2f}
                Venda: #{venda.data.get('numero_venda')}

                Acesse o sistema para receber o pagamento!

                _Mensagem enviada via MedPIX_
                        """
                        
                        enviar_whatsapp(clinica.get('whatsapp'), mensagem)
                        
                        print("✅ Clínica notificada sobre parcela 2")
                except Exception as e:
                    print(f"⚠️ Erro ao notificar: {e}")
            
            ui.notification_show(
                f"✅ {len(itens_para_atender)} procedimento(s) registrado(s) como atendido(s)!",
                type="message",
                duration=5
            )
            
            atendimento_trigger.set(atendimento_trigger() + 1) 
            # =========================================
            
        except Exception as e:
            print(f"Erro registrar_atendimento: {e}")
            import traceback
            traceback.print_exc()
            ui.notification_show(f"❌ Erro: {str(e)}", type="error")
            
    @output
    @render.ui
    def lista_vendas_pagamento():
        try:
            user = user_data()
            if not user or not supabase:
                return ui.div()
            
            # Busca vendas do vendedor
            query = supabase.table('vendas').select(
                '*, clientes(nome_completo, cpf), clinicas(razao_social)'
            ).eq('vendedor_id', user['id']).eq('tipo', 'venda')
            
            # Aplica filtros
            filtro = input.filtro_status_pagamento()
            if filtro == "pendente":
                query = query.eq('pagamento_informado', False)
            elif filtro == "informado":
                query = query.eq('pagamento_informado', True).eq('pagamento_confirmado', False)
            elif filtro == "confirmado":
                query = query.eq('pagamento_confirmado', True)
            
            # Busca por código
            busca = input.buscar_venda_codigo()
            if busca:
                query = query.ilike('numero_venda', f'%{busca}%')
            
            result = query.order('criado_em', desc=True).limit(50).execute()
            
            if not result.data:
                return ui.div(
                    {"style": "text-align: center; padding: 3rem; color: #94a3b8;"},
                    ui.h5("🔭 Nenhuma venda encontrada"),
                    ui.p("As vendas aparecerão aqui após serem finalizadas")
                )
            
            cards = []
            for idx, venda in enumerate(result.data):
                # Status
                if venda.get('pagamento_confirmado'):
                    status = "✅ Confirmado"
                    cor_status = "#10b981"
                    mostrar_botao = False
                elif venda.get('pagamento_informado'):
                    status = "🟡 Aguardando Confirmação"
                    cor_status = "#f59e0b"
                    mostrar_botao = False
                else:
                    status = "⏳ Pendente"
                    cor_status = "#ef4444"
                    mostrar_botao = True
                
                cliente_nome = venda.get('clientes', {}).get('nome_completo', 'N/A')
                clinica_nome = venda.get('clinicas', {}).get('razao_social', 'N/A')
                venda_id = str(venda['id'])
                
                # Cria card
                card = ui.div(
                    {"class": "card-custom", "style": f"margin-bottom: 1rem; border-left: 4px solid {cor_status};"},
                    ui.row(
                        ui.column(8,
                            ui.h6(f"📄 {venda['numero_venda']}", style="margin: 0 0 0.5rem 0;"),
                            ui.p(f"👤 Cliente: {cliente_nome}", style="margin: 0.25rem 0; font-size: 0.9rem;"),
                            ui.p(f"🏥 Clínica: {clinica_nome}", style="margin: 0.25rem 0; font-size: 0.9rem;"),
                            ui.p(f"💰 Valor: {formatar_moeda(venda['valor_total'])}", 
                                 style="margin: 0.25rem 0; font-size: 0.9rem; font-weight: 600;")
                        ),
                        ui.column(4,
                            ui.div(
                                {"style": "text-align: right;"},
                                ui.p(status, style=f"margin: 0 0 1rem 0; color: {cor_status}; font-weight: 600;"),
                                
                                # BOTÃO COM ONCLICK JAVASCRIPT
                                ui.tags.button(
                                    "💰 Informar Pagamento",
                                    class_="btn btn-primary w-100",
                                    onclick=f"Shiny.setInputValue('venda_paga_id', '{venda_id}', {{priority: 'event'}})",
                                    style="font-weight: 600;"
                                ) if mostrar_botao else ui.div(
                                    {"class": "btn btn-secondary w-100", "style": "font-weight: 600;"},
                                    "✅ Confirmado" if venda.get('pagamento_confirmado') else "⏳ Aguardando"
                                )
                            )
                        )
                    )
                )
                cards.append(card)
            
            return ui.div(*cards)
            
        except Exception as e:
            print(f"Erro lista_vendas_pagamento: {e}")
            import traceback
            traceback.print_exc()
            return ui.div(ui.p(f"Erro: {str(e)}", style="color: red;"))

    @reactive.Effect
    def _monitor_pagamento_click():
        """Monitora quando um botão de pagamento é clicado via JavaScript"""
        try:
            # Tenta pegar o valor do input customizado
            venda_id = None
            try:
                venda_id = input.venda_paga_id()
            except:
                return
            
            if not venda_id:
                return
            
            print(f"\n{'='*60}")
            print(f"💳 INFORMAR PAGAMENTO - DEBUG")
            print(f"{'='*60}")
            print(f"Venda ID recebido: {venda_id}")
            
            user = user_data()
            if not user or not supabase:
                print("❌ User ou Supabase não disponível")
                return
            
            # Verifica se já foi informado
            check = supabase.table('vendas').select('pagamento_informado, numero_venda').eq('id', venda_id).execute()
            
            if not check.data:
                print("❌ Venda não encontrada")
                ui.notification_show("❌ Venda não encontrada!", type="error")
                return
            
            venda_info = check.data[0]
            numero_venda = venda_info.get('numero_venda', 'N/A')
            
            if venda_info.get('pagamento_informado'):
                print("⚠️ Pagamento já foi informado")
                ui.notification_show("⚠️ Pagamento já foi informado!", type="warning")
                return
            
            # Atualiza venda
            print("✅ Atualizando venda no banco...")
            supabase.table('vendas').update({
                'pagamento_informado': True,
                'data_pagamento_informado': datetime.now().isoformat(),
                'vendedor_informou_id': user['id']
            }).eq('id', venda_id).execute()
            
            print(f"✅ Pagamento informado com sucesso!")
            print(f"{'='*60}\n")
            
            ui.notification_show(
                f"✅ Pagamento da venda {numero_venda} informado com sucesso!\n"
                f"⏳ Aguardando confirmação do superusuário.",
                type="message",
                duration=5
            )
            
        except Exception as e:
            print(f"❌ Erro em _monitor_pagamento_click: {e}")
            import traceback
            traceback.print_exc()
            ui.notification_show(f"❌ Erro: {str(e)}", type="error")

    @output
    @render.ui
    def select_venda_para_pagamento():
        """Select com vendas pendentes de pagamento"""
        try:
            user = user_data()
            if not user or not supabase:
                return ui.div()
            
            result = supabase.table('vendas').select(
                'id, numero_venda, valor_total'
            ).eq('vendedor_id', user['id']).eq('tipo', 'venda').eq(
                'pagamento_informado', False
            ).order('criado_em', desc=True).execute()
            
            if not result.data:
                return ui.div(
                    {"class": "alert alert-info"},
                    "✅ Não há vendas pendentes de informação de pagamento!"
                )
            
            choices = {
                str(v['id']): f"{v['numero_venda']} - {formatar_moeda(v['valor_total'])}"
                for v in result.data
            }
            
            return ui.div(
                ui.input_select(
                    "venda_para_informar_pagamento",
                    "Selecione a venda para informar pagamento:",
                    choices=choices
                ),
                ui.input_action_button(
                    "btn_confirmar_pagamento_vendedor",
                    "💰 Confirmar que Cliente Pagou",
                    class_="btn-primary w-100 mt-3"
                )
            )
            
        except Exception as e:
            print(f"Erro select_venda_para_pagamento: {e}")
            return ui.div()

    # Effect para o botão único
    @reactive.Effect
    @reactive.event(input.btn_confirmar_pagamento_vendedor)
    def confirmar_pagamento_vendedor():
        try:
            venda_id = input.venda_para_informar_pagamento()
            if not venda_id:
                ui.notification_show("⚠️ Selecione uma venda!", type="warning")
                return
            
            informar_pagamento(venda_id)
            
        except Exception as e:
            print(f"Erro confirmar_pagamento_vendedor: {e}")
            ui.notification_show(f"❌ Erro: {str(e)}", type="error")

    # ========== INFORMAR PAGAMENTO ==========
    def informar_pagamento(venda_id):
        try:
            user = user_data()
            if not user or not supabase:
                return
            
            # Atualiza venda
            supabase.table('vendas').update({
                'pagamento_informado': True,
                'data_pagamento_informado': datetime.now().isoformat(),
                'vendedor_informou_id': user['id']
            }).eq('id', venda_id).execute()
            
            ui.notification_show(
                "✅ Pagamento informado com sucesso!\n⏳ Aguardando confirmação do superusuário.",
                type="message",
                duration=5
            )
            
        except Exception as e:
            print(f"Erro informar_pagamento: {e}")
            ui.notification_show(f"❌ Erro: {str(e)}", type="error")
            

    @output
    @render.text
    def stat_aguardando_confirmacao():
        try:
            if not supabase: 
                return "0"
            result = supabase.table('vendas').select('id', count='exact').eq('pagamento_informado', True).eq('pagamento_confirmado', False).execute()
            count = result.count if hasattr(result, 'count') and result.count is not None else 0
            return safe_str(count)
        except Exception as e:
            print(f"Erro stat_aguardando_confirmacao: {e}")
            return "0"

    @output
    @render.text
    def stat_confirmados_hoje():
        try:
            if not supabase: 
                return "0"
            hoje = date.today().isoformat()
            result = supabase.table('vendas').select('id', count='exact').eq('pagamento_confirmado', True).gte('data_pagamento_confirmado', f'{hoje}T00:00:00').execute()
            count = result.count if hasattr(result, 'count') and result.count is not None else 0
            return safe_str(count)
        except Exception as e:
            print(f"Erro stat_confirmados_hoje: {e}")
            return "0"

    @output
    @render.text
    def stat_total_confirmados():
        try:
            if not supabase: 
                return "0"
            result = supabase.table('vendas').select('id', count='exact').eq('pagamento_confirmado', True).execute()
            count = result.count if hasattr(result, 'count') and result.count is not None else 0
            return safe_str(count)
        except Exception as e:
            print(f"Erro stat_total_confirmados: {e}")
            return "0"
        
    @output
    @render.ui
    def lista_confirmacao_pagamentos():
        try:
            if not supabase:
                return ui.div()
            
            # Query base
            query = supabase.table('vendas').select(
                '*, clientes(nome_completo, cpf), clinicas(razao_social), usuarios!vendas_vendedor_id_fkey(nome)'
            ).eq('tipo', 'venda')
            
            # Filtros
            filtro = input.filtro_confirmacao()
            if filtro == "pendentes":
                query = query.eq('pagamento_informado', True).eq('pagamento_confirmado', False)
            elif filtro == "confirmados":
                query = query.eq('pagamento_confirmado', True)
            
            # Busca
            busca = input.buscar_confirmacao()
            if busca:
                query = query.or_(f'numero_venda.ilike.%{busca}%')
            
            result = query.order('data_pagamento_informado', desc=True).limit(100).execute()
            
            if not result.data:
                return ui.div(
                    {"style": "text-align: center; padding: 3rem; color: #94a3b8;"},
                    ui.h5("🔭 Nenhum pagamento encontrado"),
                    ui.p("Os pagamentos informados aparecerão aqui")
                )
            
            cards = []
            for venda in result.data:
                confirmado = venda.get('pagamento_confirmado', False)
                cor_border = "#10b981" if confirmado else "#f59e0b"
                
                cliente = venda.get('clientes')
                cliente_nome = cliente.get('nome_completo', 'N/A') if cliente else 'N/A'

                clinica = venda.get('clinicas')
                clinica_nome = clinica.get('razao_social', 'N/A') if clinica else 'N/A'

                vendedor = venda.get('usuarios')
                vendedor_nome = vendedor.get('nome', 'N/A') if vendedor else 'N/A'
                
                data_info = venda.get('data_pagamento_informado')
                data_conf = venda.get('data_pagamento_confirmado')
                venda_id = str(venda['id'])
                
                card = ui.div(
                    {"class": "card-custom", "style": f"margin-bottom: 1rem; border-left: 4px solid {cor_border};"},
                    ui.row(
                        ui.column(9,
                            ui.row(
                                ui.column(6,
                                    ui.h6(f"📄 {venda['numero_venda']}", style="margin: 0 0 0.5rem 0;"),
                                    ui.p(f"👤 Cliente: {cliente_nome}", style="margin: 0.25rem 0; font-size: 0.9rem;"),
                                    ui.p(f"🏥 Clínica: {clinica_nome}", style="margin: 0.25rem 0; font-size: 0.9rem;")
                                ),
                                ui.column(6,
                                    ui.p(f"💼 Vendedor: {vendedor_nome}", style="margin: 0.25rem 0; font-size: 0.9rem;"),
                                    ui.p(f"💰 Valor: {formatar_moeda(venda['valor_total'])}", 
                                         style="margin: 0.25rem 0; font-size: 0.9rem; font-weight: 600; color: #1DD1A1;"),
                                    ui.p(f"📅 Informado: {pd.to_datetime(data_info).strftime('%d/%m/%Y %H:%M') if data_info else '-'}", 
                                         style="margin: 0.25rem 0; font-size: 0.85rem; color: #546E7A;") if data_info else None,
                                    ui.p(f"✅ Confirmado: {pd.to_datetime(data_conf).strftime('%d/%m/%Y %H:%M') if data_conf else '-'}", 
                                         style="margin: 0.25rem 0; font-size: 0.85rem; color: #10b981;") if data_conf else None
                                )
                            )
                        ),
                        ui.column(3,
                            ui.div(
                                {"style": "text-align: right;"},
                                ui.p("✅ Confirmado" if confirmado else "⏳ Pendente", 
                                     style=f"margin: 0 0 1rem 0; font-weight: 600; color: {cor_border};"),
                                
                                # BOTÃO COM ONCLICK JAVASCRIPT
                                ui.tags.button(
                                    "✅ Confirmar Pagamento",
                                    class_="btn btn-success w-100",
                                    onclick=f"Shiny.setInputValue('confirmar_paga_id', '{venda_id}', {{priority: 'event'}})",
                                    style="font-weight: 600;"
                                ) if not confirmado else ui.div(
                                    {"class": "btn btn-secondary w-100", "style": "font-weight: 600;"},
                                    "Confirmado"
                                )
                            )
                        )
                    )
                )
                cards.append(card)
            
            return ui.div(*cards)
            
        except Exception as e:
            print(f"Erro lista_confirmacao_pagamentos: {e}")
            import traceback
            traceback.print_exc()
            return ui.div(ui.p(f"Erro: {str(e)}", style="color: red;"))

# ========== EFFECT PARA CONFIRMAR PAGAMENTO (SUPERUSUÁRIO) ==========
    @reactive.Effect
    def _monitor_confirmacao_click():
        """Monitora quando um botão de confirmação é clicado via JavaScript"""
        try:
            venda_id = None
            try:
                venda_id = input.confirmar_paga_id()
            except:
                return
            
            if not venda_id:
                return
            
            print(f"\n{'='*60}")
            print(f"✅ CONFIRMAR PAGAMENTO - DEBUG")
            print(f"{'='*60}")
            print(f"Venda ID recebido: {venda_id}")
            
            user = user_data()
            if not user or not supabase:
                print("❌ User ou Supabase não disponível")
                return
            
            # 1. BUSCA DADOS DA VENDA (INCLUINDO tipo_compra)
            check_result = supabase.table('vendas').select('pagamento_confirmado, numero_venda, tipo_compra').eq('id', venda_id).execute()
            
            if not check_result.data:
                print("❌ Venda não encontrada")
                ui.notification_show("❌ Venda não encontrada!", type="error")
                return
            
            venda_info = check_result.data[0]
            numero_venda = venda_info.get('numero_venda', 'N/A')
            tipo_compra = venda_info.get('tipo_compra', 'proprio')
            
            if venda_info.get('pagamento_confirmado'):
                print("⚠️ Pagamento já foi confirmado")
                ui.notification_show("⚠️ Pagamento já foi confirmado!", type="warning")
                return
            
            # 2. ATUALIZA A VENDA (MARCA COMO PAGA)
            print("✅ Confirmando pagamento no banco...")
            update_response = supabase.table('vendas').update({
                'pagamento_confirmado': True,
                'data_pagamento_confirmado': datetime.now().isoformat(),
                'superusuario_confirmou_id': user['id']
            }).eq('id', venda_id).execute()
            
            if not update_response.data:
                print("❌ Erro ao atualizar status da venda")
                ui.notification_show("❌ Erro ao salvar confirmação!", type="error")
                return

            print(f"✅ Pagamento confirmado com sucesso!")
            
            # 3. GERA E SALVA A IMAGEM COMPARTILHÁVEL (SE FOR PARA TERCEIROS)
            if tipo_compra != 'proprio':
                print(f"🖼️ [ADMIN] Compra para terceiros detectada. Gerando imagem para Venda: {numero_venda}")
                try:
                    # Busca dados completos para a imagem (de forma mais segura)
                    venda_completa_result = supabase.table('vendas').select(
                        '*, clientes(*), clinicas(*), itens_venda(*)'
                    ).eq('id', venda_id).execute()
                    
                    if venda_completa_result.data:
                        venda_completa = venda_completa_result.data[0] # Pega o primeiro
                        
                        print("🖼️ [ADMIN] Dados completos da venda obtidos. Chamando gerar_imagem_compartilhavel...")
                        
                        img_bytes = gerar_imagem_compartilhavel(
                            venda_data=venda_completa,
                            cliente_data=venda_completa.get('clientes', {}),
                            clinica_data=venda_completa.get('clinicas', {}),
                            itens=venda_completa.get('itens_venda', [])
                        )
                        
                        print(f"🖼️ [ADMIN] Bytes da imagem recebidos: {len(img_bytes)} bytes.")
                        
                        storage_filename = f"medpix_benef_{numero_venda.replace('/', '_')}_{venda_id[:6]}.png"
                        # Garante que o nome do bucket está correto
                        bucket_name = "imagens-compartilhadas" 
                        
                        print(f"🖼️ [ADMIN] Fazendo upload para {bucket_name}/{storage_filename}...")
                        
                        supabase.storage.from_(bucket_name).upload(
                            path=storage_filename,
                            file=img_bytes,
                            file_options={"content-type": "image/png", "upsert": "true"}
                        )
                        
                        public_url = supabase.storage.from_(bucket_name).get_public_url(storage_filename)
                        print(f"🖼️ [ADMIN] Imagem salva com sucesso! URL: {public_url}")
                        
                        # Salva a URL na tabela 'vendas'
                        supabase.table('vendas').update({
                            'url_imagem_beneficiario': public_url
                        }).eq('id', venda_id).execute()
                        
                        print(f"✅ [ADMIN] URL da imagem salva na venda {venda_id}")
                        
                    else:
                        print(f"❌ [ADMIN] Não foi possível buscar dados completos da venda {venda_id} para gerar imagem.")

                except Exception as e_img:
                    print(f"❌ ERRO CRÍTICO AO GERAR/SALVAR IMAGEM: {e_img}")
                    import traceback
                    traceback.print_exc()
            
            # ... (resto da função) ...
            
            # 4. NOTIFICA O ADMIN
            ui.notification_show(
                f"✅ Pagamento da venda {numero_venda} confirmado com sucesso!\n"
                f"🩺 Cliente liberado para atendimento na clínica.",
                type="message",
                duration=5
            )
            
            # 5. ATUALIZA A UI DO CLIENTE (MUITO IMPORTANTE)
            # Isso força a função `lista_minhas_compras_cliente` a rodar novamente
            print("🔄 Disparando trigger 'minhas_compras_trigger' para o cliente.")
            minhas_compras_trigger.set(minhas_compras_trigger() + 1)
            
        except Exception as e:
            print(f"❌ Erro em _monitor_confirmacao_click: {e}")
            import traceback
            traceback.print_exc()
            ui.notification_show(f"❌ Erro: {str(e)}", type="error")
            
# ========== CONFIGURAÇÕES DA CLÍNICA ==========
    
    @output
    @render.text
    def status_gps_clinica():
        """Mostra status do GPS da clínica"""
        try:
            user = user_data()
            if not user or not supabase:
                return "❌ Erro ao carregar"
            
            clinica_result = supabase.table('clinicas').select(
                'latitude, longitude, endereco_rua, endereco_numero, endereco_complemento, endereco_bairro, endereco_cidade, endereco_estado, endereco_cep'
            ).eq('usuario_id', user['id']).execute()
            
            if not clinica_result.data:
                return "❌ Clínica não encontrada"
            
            clinica = clinica_result.data[0]
            lat = clinica.get('latitude')
            lon = clinica.get('longitude')

            # Monta endereço completo - TRATA NULL
            rua = clinica.get('endereco_rua') or ''
            numero = clinica.get('endereco_numero') or ''
            complemento = clinica.get('endereco_complemento') or ''
            bairro = clinica.get('endereco_bairro') or ''
            cidade = clinica.get('endereco_cidade') or ''
            estado = clinica.get('endereco_estado') or ''
            cep = clinica.get('endereco_cep') or ''

            # Formata endereço
            partes = []
            if rua and numero:
                partes.append(f"{rua}, {numero}")
            elif rua:
                partes.append(rua)
                
            if complemento:
                partes.append(complemento)
            if bairro:
                partes.append(bairro)
                
            endereco_completo = ' - '.join(partes)
            
            if lat and lon:
                return f"✅ GPS Configurado!\n\n📍 Latitude: {lat:.6f}\n📍 Longitude: {lon:.6f}\n\n📫 {endereco_completo}\n🏙️ {cidade}/{estado}\n📮 CEP: {cep}"
            else:
                return f"⚠️ GPS NÃO configurado\n\n📫 Endereço: {endereco_completo or 'Não cadastrado'}\n🏙️ {cidade}/{estado}\n📮 CEP: {cep}\n\nClique no botão abaixo para atualizar automaticamente."
                
        except Exception as e:
            print(f"Erro status_gps_clinica: {e}")
            return f"❌ Erro: {str(e)}"

    @reactive.Effect
    @reactive.event(input.btn_atualizar_gps)
    def _atualizar_gps_clinica():
        """Atualiza GPS da clínica automaticamente"""
        try:
            user = user_data()
            if not user or not supabase:
                ui.notification_show("❌ Erro de autenticação", type="error")
                return
            
            # Busca dados da clínica
            clinica_result = supabase.table('clinicas').select(
                'id, endereco_rua, endereco_numero, endereco_complemento, endereco_bairro, endereco_cidade, endereco_estado, latitude, longitude'
            ).eq('usuario_id', user['id']).execute()
            
            if not clinica_result.data:
                ui.notification_show("❌ Clínica não encontrada", type="error")
                return
            
            clinica = clinica_result.data[0]
            endereco = clinica.get('endereco_completo', '').strip()
            cidade = clinica.get('endereco_cidade', '').strip()
            estado = clinica.get('endereco_estado', '').strip()
            
            clinica = clinica_result.data[0]

            # Monta endereço completo - TRATA NULL
            rua = (clinica.get('endereco_rua') or '').strip()
            numero = (clinica.get('endereco_numero') or '').strip()
            complemento = (clinica.get('endereco_complemento') or '').strip()
            bairro = (clinica.get('endereco_bairro') or '').strip()
            cidade = (clinica.get('endereco_cidade') or '').strip()
            estado = (clinica.get('endereco_estado') or '').strip()

            # Formata para geocoding (quanto mais detalhado, melhor)
            partes = []
            if rua and numero:
                partes.append(f"{rua}, {numero}")
            elif rua:
                partes.append(rua)
                
            if bairro:
                partes.append(bairro)
                
            endereco_completo = ', '.join(partes) if partes else ''

            if not cidade or not estado:
                ui.notification_show(
                    "⚠️ Cidade ou estado não cadastrados!\n"
                    "Complete o cadastro primeiro.",
                    type="warning",
                    duration=8
                )
                return

            if not rua:
                ui.notification_show(
                    "⚠️ Rua não cadastrada!\n"
                    "Adicione o endereço (rua e número) para obter GPS preciso.",
                    type="warning",
                    duration=8
                )
                return
            
            print(f"\n{'='*60}")
            print(f"🔄 ATUALIZANDO GPS DA CLÍNICA")
            print(f"{'='*60}")
            print(f"Endereço: {endereco_completo}")
            print(f"Cidade: {cidade}/{estado}")

            # Chama função de geocoding
            lat, lon = obter_coordenadas_por_endereco(endereco_completo, cidade, estado)
            
            if lat and lon:
                # Atualiza no banco
                supabase.table('clinicas').update({
                    'latitude': lat,
                    'longitude': lon
                }).eq('id', clinica['id']).execute()
                
                print(f"✅ GPS atualizado: {lat}, {lon}")
                print(f"{'='*60}\n")
                
                ui.notification_show(
                    f"✅ GPS Atualizado com Sucesso!\n\n"
                    f"📍 Lat: {lat:.6f}\n"
                    f"📍 Lon: {lon:.6f}\n\n"
                    f"Sua clínica agora aparece nos resultados de busca por proximidade!",
                    type="message",
                    duration=10
                )
            else:
                print(f"❌ Não foi possível obter coordenadas")
                print(f"{'='*60}\n")
                
                ui.notification_show(
                    f"❌ Não conseguimos localizar o endereço.\n\n"
                    f"Verifique se o endereço está correto:\n"
                    f"{endereco_completo}, {cidade}/{estado}\n\n"
                    f"Tente ser mais específico (ex: 'Rua Nome Silva, 123, Centro')",
                    type="error",
                    duration=10
                )
                
        except Exception as e:
            print(f"❌ Erro ao atualizar GPS: {e}")
            import traceback
            traceback.print_exc()
            ui.notification_show(f"❌ Erro: {str(e)}", type="error")

# ========== EDIÇÃO DE DADOS DA CLÍNICA ==========
    
    @output
    @render.ui
    def form_editar_clinica():
        """Formulário para editar dados da clínica - OTIMIZADO"""
        try:
            user = user_data()
            if not user or not supabase:
                return ui.div("❌ Erro ao carregar")
            
            # Busca dados da clínica
            clinica_result = supabase.table('clinicas').select('*').eq('usuario_id', user['id']).execute()
            
            if not clinica_result.data:
                return ui.div("❌ Clínica não encontrada")
            
            clinica = clinica_result.data[0]
            
            return ui.div(
                # ========== SEÇÃO 1: IDENTIFICAÇÃO ==========
                ui.div(
                    {"style": "background: #f8fafc; padding: 1.5rem; border-radius: 0.75rem; margin-bottom: 1.5rem; border: 2px solid #e2e8f0;"},
                    ui.h6("🏥 Identificação", style="margin: 0 0 1rem 0; color: #1e40af; font-weight: 600; font-size: 1rem;"),
                    
                    ui.row(
                        ui.column(6,
                            ui.input_text("edit_razao_social", "Razão Social*", 
                                         value=clinica.get('razao_social', ''),
                                         placeholder="Empresa LTDA")
                        ),
                        ui.column(6,
                            ui.input_text("edit_nome_fantasia", "Nome Fantasia*", 
                                         value=clinica.get('nome_fantasia', ''),
                                         placeholder="Nome da Clínica")
                        )
                    )
                ),
                
                # ========== SEÇÃO 2: CONTATO ==========
                ui.div(
                    {"style": "background: #f8fafc; padding: 1.5rem; border-radius: 0.75rem; margin-bottom: 1.5rem; border: 2px solid #e2e8f0;"},
                    ui.h6("📞 Contato", style="margin: 0 0 1rem 0; color: #1e40af; font-weight: 600; font-size: 1rem;"),
                    
                    ui.row(
                        ui.column(4,
                            ui.input_text("edit_email", "Email*", 
                                         value=clinica.get('email', ''),
                                         placeholder="contato@clinica.com")
                        ),
                        ui.column(4,
                            ui.input_text("edit_telefone", "Telefone*", 
                                         value=clinica.get('telefone', ''),
                                         placeholder="(27) 3333-4444")
                        ),
                        ui.column(4,
                            ui.input_text("edit_whatsapp", "WhatsApp", 
                                         value=clinica.get('whatsapp', ''),
                                         placeholder="(27) 99999-8888")
                        )
                    )
                ),
                
                # ========== SEÇÃO 3: ENDEREÇO ==========
                ui.div(
                    {"style": "background: #f8fafc; padding: 1.5rem; border-radius: 0.75rem; margin-bottom: 1.5rem; border: 2px solid #e2e8f0;"},
                    ui.h6("📍 Endereço Completo", style="margin: 0 0 1rem 0; color: #1e40af; font-weight: 600; font-size: 1rem;"),
                    
                    # Linha 1: Rua e Número
                    ui.row(
                        ui.column(9,
                            ui.input_text("edit_endereco_rua", "Rua/Avenida*", 
                                         value=clinica.get('endereco_rua', ''),
                                         placeholder="Ex: Rua Sete de Setembro")
                        ),
                        ui.column(3,
                            ui.input_text("edit_endereco_numero", "Número*", 
                                         value=clinica.get('endereco_numero', ''),
                                         placeholder="Ex: 500")
                        )
                    ),
                    
                    # Linha 2: Complemento e Bairro
                    ui.row(
                        ui.column(5,
                            ui.input_text("edit_endereco_complemento", "Complemento", 
                                         value=clinica.get('endereco_complemento', ''),
                                         placeholder="Ex: Sala 201")
                        ),
                        ui.column(7,
                            ui.input_text("edit_endereco_bairro", "Bairro*", 
                                         value=clinica.get('endereco_bairro', ''),
                                         placeholder="Ex: Centro")
                        )
                    ),
                    
                    # Linha 3: Estado, Cidade e CEP
                    ui.row(
                        ui.column(3,
                            ui.input_select("edit_endereco_estado", "Estado*",
                                           choices={
                                               "": "Selecione...",
                                               "AC": "AC", "AL": "AL", "AP": "AP", "AM": "AM",
                                               "BA": "BA", "CE": "CE", "DF": "DF", "ES": "ES",
                                               "GO": "GO", "MA": "MA", "MT": "MT", "MS": "MS",
                                               "MG": "MG", "PA": "PA", "PB": "PB", "PR": "PR",
                                               "PE": "PE", "PI": "PI", "RJ": "RJ", "RN": "RN",
                                               "RS": "RS", "RO": "RO", "RR": "RR", "SC": "SC",
                                               "SP": "SP", "SE": "SE", "TO": "TO"
                                           },
                                           selected=clinica.get('endereco_estado', ''))
                        ),
                        ui.column(6,
                            ui.input_text("edit_endereco_cidade", "Cidade*", 
                                         value=clinica.get('endereco_cidade', ''),
                                         placeholder="Ex: Vitória")
                        ),
                        ui.column(3,
                            ui.input_text("edit_endereco_cep", "CEP*", 
                                         value=clinica.get('endereco_cep', ''),
                                         placeholder="00000-000")
                        )
                    )
                ),
                
                # ========== SEÇÃO 4: RESPONSÁVEL ==========
                ui.div(
                    {"style": "background: #f8fafc; padding: 1.5rem; border-radius: 0.75rem; margin-bottom: 1rem; border: 2px solid #e2e8f0;"},
                    ui.h6("👤 Responsável pela Clínica", style="margin: 0 0 1rem 0; color: #1e40af; font-weight: 600; font-size: 1rem;"),
                    
                    ui.row(
                        ui.column(7,
                            ui.input_text("edit_responsavel_nome", "Nome Completo", 
                                         value=clinica.get('responsavel_nome', ''),
                                         placeholder="Ex: Dr. João Silva")
                        ),
                        ui.column(5,
                            ui.input_text("edit_responsavel_contato", "Telefone", 
                                         value=clinica.get('responsavel_contato', ''),
                                         placeholder="Ex: (27) 98888-7777")
                        )
                    )
                ),
                
                # ========== AVISO ==========
                ui.div(
                    {"style": "background: linear-gradient(135deg, #fef3c7, #fde68a); padding: 1rem 1.25rem; border-radius: 0.5rem; border-left: 4px solid #f59e0b;"},
                    ui.p("💡 Após salvar, clique em 'Atualizar GPS' abaixo para recalcular sua localização automaticamente.", 
                         style="margin: 0; color: #92400e; font-size: 0.9rem; font-weight: 500;")
                )
            )
            
        except Exception as e:
            print(f"Erro form_editar_clinica: {e}")
            import traceback
            traceback.print_exc()
            return ui.div(
                {"class": "alert alert-danger"},
                ui.h5("❌ Erro ao carregar formulário"),
                ui.p(str(e))
            )

    @reactive.Effect
    @reactive.event(input.btn_salvar_dados_clinica)
    def _salvar_dados_clinica():
        """Salva alterações nos dados da clínica"""
        try:
            user = user_data()
            if not user or not supabase:
                ui.notification_show("❌ Erro de autenticação", type="error")
                return
            
            # Coleta dados do formulário
            razao_social = input.edit_razao_social()
            nome_fantasia = input.edit_nome_fantasia()
            email = input.edit_email()
            telefone = input.edit_telefone()
            whatsapp = input.edit_whatsapp()
            
            endereco_rua = input.edit_endereco_rua()
            endereco_numero = input.edit_endereco_numero()
            endereco_complemento = input.edit_endereco_complemento()
            endereco_bairro = input.edit_endereco_bairro()
            endereco_cidade = input.edit_endereco_cidade()
            endereco_estado = input.edit_endereco_estado()
            endereco_cep = input.edit_endereco_cep()
            
            responsavel_nome = input.edit_responsavel_nome()
            responsavel_contato = input.edit_responsavel_contato()
            
            # Validações
            campos_vazios = []
            if not razao_social: campos_vazios.append("Razão Social")
            if not nome_fantasia: campos_vazios.append("Nome Fantasia")
            if not email: campos_vazios.append("Email")
            if not telefone: campos_vazios.append("Telefone")
            if not endereco_rua: campos_vazios.append("Rua")
            if not endereco_numero: campos_vazios.append("Número")
            if not endereco_bairro: campos_vazios.append("Bairro")
            if not endereco_cidade: campos_vazios.append("Cidade")
            if not endereco_estado: campos_vazios.append("Estado")
            if not endereco_cep: campos_vazios.append("CEP")
            
            if campos_vazios:
                ui.notification_show(
                    f"⚠️ Preencha os campos obrigatórios:\n" + ", ".join(campos_vazios),
                    type="warning",
                    duration=8
                )
                return
            
            print(f"\n{'='*60}")
            print(f"💾 SALVANDO DADOS DA CLÍNICA")
            print(f"{'='*60}")
            print(f"Razão Social: {razao_social}")
            print(f"Nome Fantasia: {nome_fantasia}")
            print(f"Email: {email}")
            print(f"Endereço: {endereco_rua}, {endereco_numero}")
            
            # Atualiza no banco
            supabase.table('clinicas').update({
                'razao_social': razao_social,
                'nome_fantasia': nome_fantasia,
                'email': email,
                'telefone': telefone,
                'whatsapp': whatsapp,
                'endereco_rua': endereco_rua,
                'endereco_numero': endereco_numero,
                'endereco_complemento': endereco_complemento,
                'endereco_bairro': endereco_bairro,
                'endereco_cidade': endereco_cidade,
                'endereco_estado': endereco_estado,
                'endereco_cep': endereco_cep,
                'responsavel_nome': responsavel_nome,
                'responsavel_contato': responsavel_contato
            }).eq('usuario_id', user['id']).execute()
            
            print(f"✅ Dados salvos com sucesso!")
            print(f"{'='*60}\n")
            
            ui.notification_show(
                f"✅ Dados atualizados com sucesso!\n\n"
                f"🏥 {nome_fantasia}\n"
                f"📍 {endereco_rua}, {endereco_numero} - {endereco_cidade}/{endereco_estado}\n\n"
                f"💡 Clique em 'Atualizar GPS' para recalcular sua localização.",
                type="message",
                duration=10
            )
            
        except Exception as e:
            print(f"❌ Erro ao salvar dados: {e}")
            import traceback
            traceback.print_exc()
            ui.notification_show(f"❌ Erro ao salvar: {str(e)}", type="error")

# ===================================================================
    # === 🎁 INÍCIO - LÓGICA DE PACOTES DA CLÍNICA ===
    # ===================================================================

    @output
    @render.ui
    def pacote_form_ui():
        """Renderiza o formulário de criação/edição de pacotes."""
        try:
            user = user_data()
            if not user or not supabase:
                return ui.div("Erro: Usuário não autenticado.")

            # Busca a clínica do usuário
            clinica_result = supabase.table('clinicas').select('id').eq('usuario_id', user['id']).maybe_single().execute()
            if not clinica_result.data:
                return ui.div("Erro: Clínica não encontrada.")
            
            clinica_id = clinica_result.data['id']

            # Busca os procedimentos desta clínica para o select
            procs_result = supabase.table('procedimentos').select('id, nome, preco').eq('clinica_id', clinica_id).eq('ativo', True).order('nome').execute()
            
            choices = {}
            if procs_result.data:
                for proc in procs_result.data:
                    choices[str(proc['id'])] = f"{proc['nome']} - {formatar_moeda(proc['preco'])}"

            # Verifica se está em modo de edição
            edit_id = pacote_editando_id()
            pacote_atual = None
            selected_procs = []
            
            if edit_id:
                # Busca dados do pacote
                pacote_res = supabase.table('pacotes').select('*').eq('id', edit_id).maybe_single().execute()
                if pacote_res.data:
                    pacote_atual = pacote_res.data
                
                # Busca itens do pacote
                itens_res = supabase.table('pacotes_itens').select('procedimento_id').eq('pacote_id', edit_id).execute()
                if itens_res.data:
                    selected_procs = [str(item['procedimento_id']) for item in itens_res.data]

            return ui.div(
                {"class": "card-custom", "style": "background: #f8fafc; border: 2px solid #e2e8f0;"},
                ui.row(
                    ui.column(6,
                        ui.input_text("pacote_nome", "Nome do Pacote*", 
                                      value=pacote_atual['nome'] if pacote_atual else "")
                    ),
                    ui.column(6,
                        ui.input_numeric("pacote_valor_desconto", "Desconto (R$)", 
                                         value=float(pacote_atual['valor_desconto']) if pacote_atual else 0, 
                                         min=0, step=1)
                    )
                ),
                ui.input_text_area("pacote_descricao", "Descrição (Opcional)", 
                                   value=pacote_atual['descricao'] if pacote_atual else "", 
                                   rows=2),
                
                ui.input_selectize(
                    "pacote_procedimentos_select",
                    "Selecione os Procedimentos*",
                    choices=choices,
                    selected=selected_procs,
                    multiple=True
                )
            )

        except Exception as e:
            print(f"❌ Erro em pacote_form_ui: {e}")
            return ui.div({"class": "alert alert-danger"}, f"Erro ao carregar formulário: {e}")

    @reactive.Effect
    @reactive.event(input.pacote_procedimentos_select, input.pacote_valor_desconto, ignore_none=False)
    def _calcular_valores_pacote():
        """Calcula e atualiza o valor base e final do pacote dinamicamente."""
        try:
            proc_ids = input.pacote_procedimentos_select()
            desconto = input.pacote_valor_desconto() or 0
            
            if not proc_ids:
                pacote_valores_base.set({"base": 0, "final": 0, "procs": {}})
                return

            # Busca os preços dos procedimentos selecionados
            result = supabase.table('procedimentos').select('id, nome, preco').in_('id', proc_ids).execute()
            
            if not result.data:
                pacote_valores_base.set({"base": 0, "final": 0, "procs": {}})
                return
            
            valor_base = 0
            procs_map = {}
            for proc in result.data:
                preco = float(proc.get('preco', 0))
                valor_base += preco
                procs_map[str(proc['id'])] = {
                    "nome": proc['nome'],
                    "preco": preco
                }
            
            valor_final = valor_base - float(desconto)
            
            # Armazena os valores calculados
            pacote_valores_base.set({
                "base": valor_base,
                "final": valor_final,
                "procs": procs_map
            })
            
        except Exception as e:
            print(f"❌ Erro ao calcular valores do pacote: {e}")
            pacote_valores_base.set({"base": 0, "final": 0, "procs": {}})

    @output
    @render.ui
    def pacote_resumo_valores():
        """Exibe o resumo de valores (Base, Desconto, Final)."""
        valores = pacote_valores_base()
        desconto = input.pacote_valor_desconto() or 0
        
        valor_base = valores.get("base", 0)
        valor_final = valores.get("final", 0)
        procs = valores.get("procs", {})

        if valor_base == 0:
            return ui.div() # Não mostra nada se não houver procedimentos

        # Lista de procedimentos no resumo
        procs_html = []
        for proc_id, info in procs.items():
            procs_html.append(
                ui.p(f"• {info['nome']} ({formatar_moeda(info['preco'])})",
                     style="margin: 0.25rem 0; font-size: 0.85rem; color: #546E7A;")
            )

        return ui.div(
            {"class": "card-custom", "style": "margin-top: 1rem; background: linear-gradient(135deg, #f0f9ff, #e0f2fe); border: 2px solid #3b82f6;"},
            ui.h6("📊 Resumo do Pacote", style="color: #1e40af; margin-bottom: 1rem;"),
            ui.div(
                {"style": "padding-bottom: 0.75rem; border-bottom: 1px solid #93c5fd;"},
                ui.h6("Procedimentos Incluídos:", style="font-size: 0.9rem; color: #1e3a8a; margin-bottom: 0.5rem;"),
                *procs_html
            ),
            ui.div(
                {"style": "padding-top: 0.75rem;"},
                ui.row(
                    ui.column(4,
                        ui.p("Valor Base:", style="margin: 0; font-size: 0.9rem; color: #546E7A;"),
                        ui.h5(formatar_moeda(valor_base), style="margin: 0; color: #1e3a8a;")
                    ),
                    ui.column(4,
                        ui.p("Desconto:", style="margin: 0; font-size: 0.9rem; color: #546E7A;"),
                        ui.h5(f"- {formatar_moeda(desconto)}", style="margin: 0; color: #ef4444;")
                    ),
                    ui.column(4,
                        {"style": "background: white; padding: 0.75rem; border-radius: 0.5rem; text-align: center; border: 2px solid #10b981;"},
                        ui.p("Valor Final:", style="margin: 0; font-size: 1rem; color: #059669; font-weight: 600;"),
                        ui.h4(formatar_moeda(valor_final), style="margin: 0; color: #10b981; font-weight: 700;")
                    )
                )
            )
        )

    @output
    @render.ui
    def pacote_btn_salvar_ui():
        """Renderiza o botão de Salvar ou Atualizar."""
        edit_id = pacote_editando_id()
        
        if edit_id:
            # Modo Edição
            return ui.div(
                ui.row(
                    ui.column(6,
                        ui.input_action_button("btn_salvar_pacote", "💾 Atualizar Pacote", 
                                              class_="btn-success w-100 mt-3")
                    ),
                    ui.column(6,
                        ui.input_action_button("btn_cancelar_edicao_pacote", "❌ Cancelar Edição", 
                                              class_="btn-secondary w-100 mt-3")
                    )
                )
            )
        else:
            # Modo Criação
            return ui.input_action_button("btn_salvar_pacote", "➕ Criar Pacote", 
                                          class_="btn-primary w-100 mt-3")

    @reactive.Effect
    @reactive.event(input.btn_cancelar_edicao_pacote)
    def _cancelar_edicao_pacote():
        """Limpa o formulário e sai do modo de edição."""
        pacote_editando_id.set(None)
        pacote_valores_base.set({"base": 0, "final": 0, "procs": {}})
        # Limpa os inputs (a UI será recarregada por `pacote_form_ui`)
        # A recarga de `pacote_form_ui` é acionada por `pacote_editando_id.set(None)`
        # É preciso forçar a atualização do trigger para garantir
        pacotes_trigger.set(pacotes_trigger() + 1)
        
        ui.notification_show("Edição cancelada.", type="warning", duration=3)


    @reactive.Effect
    @reactive.event(input.btn_salvar_pacote)
    def _salvar_pacote():
        """Cria ou atualiza um pacote no banco de dados."""
        try:
            user = user_data()
            if not user or not supabase:
                raise Exception("Autenticação necessária.")

            clinica_result = supabase.table('clinicas').select('id').eq('usuario_id', user['id']).maybe_single().execute()
            if not clinica_result.data:
                raise Exception("Clínica não encontrada.")
            
            clinica_id = clinica_result.data['id']
            edit_id = pacote_editando_id()
            
            # 1. Coletar dados
            nome = input.pacote_nome().strip()
            descricao = input.pacote_descricao().strip()
            procedimento_ids = input.pacote_procedimentos_select()
            
            # Validação
            if not nome:
                ui.notification_show("⚠️ O nome do pacote é obrigatório!", type="warning")
                return
            if not procedimento_ids:
                ui.notification_show("⚠️ Selecione pelo menos um procedimento!", type="warning")
                return

            # 2. Coletar valores calculados
            valores = pacote_valores_base()
            valor_base = valores.get("base", 0)
            valor_final = valores.get("final", 0)
            valor_desconto = input.pacote_valor_desconto() or 0
            procs_map = valores.get("procs", {}) # Mapa com preços: {'proc_id': {'nome': 'Exame', 'preco': 50}}

            if valor_final < 0:
                ui.notification_show("⚠️ O valor final não pode ser negativo!", type="warning")
                return

            # 3. Preparar dados do pacote
            pacote_data = {
                "clinica_id": clinica_id,
                "nome": nome,
                "descricao": descricao,
                "valor_base": valor_base,
                "valor_desconto": valor_desconto,
                "valor_final": valor_final,
                "ativo": True # Sempre ativo ao salvar/criar
            }

            if edit_id:
                # ====================
                # === MODO ATUALIZAR ===
                # ====================
                print(f"🔄 Atualizando pacote ID: {edit_id}")
                
                # 1. Atualiza dados do pacote
                pacote_res = supabase.table('pacotes').update(pacote_data).eq('id', edit_id).execute()
                if not pacote_res.data:
                    raise Exception("Falha ao atualizar o pacote.")
                
                pacote_id = edit_id
                
                # 2. Sincronizar itens (Remove antigos, adiciona novos)
                print("   Sincronizando itens...")
                # 2a. Remove todos os itens antigos
                supabase.table('pacotes_itens').delete().eq('pacote_id', pacote_id).execute()
                
                # 2b. Adiciona os novos itens
                itens_para_inserir = []
                for proc_id in procedimento_ids:
                    if proc_id in procs_map:
                        preco = procs_map[proc_id]['preco']
                        itens_para_inserir.append({
                            "pacote_id": pacote_id,
                            "procedimento_id": proc_id,
                            "valor_procedimento_na_epoca": preco
                        })
                
                if itens_para_inserir:
                    supabase.table('pacotes_itens').insert(itens_para_inserir).execute()
                
                print(f"   ✅ Itens sincronizados: {len(itens_para_inserir)}")
                ui.notification_show(f"✅ Pacote '{nome}' atualizado!", type="message")

            else:
                # ====================
                # === MODO CRIAR ===
                # ====================
                print(f"➕ Criando novo pacote: {nome}")
                
                # 1. Insere o pacote principal
                pacote_res = supabase.table('pacotes').insert(pacote_data).execute()
                if not pacote_res.data:
                    raise Exception("Falha ao criar o pacote.")
                
                pacote_id = pacote_res.data[0]['id']
                print(f"   ID do pacote: {pacote_id}")

                # 2. Insere os itens do pacote
                itens_para_inserir = []
                for proc_id in procedimento_ids:
                    if proc_id in procs_map:
                        preco = procs_map[proc_id]['preco']
                        itens_para_inserir.append({
                            "pacote_id": pacote_id,
                            "procedimento_id": proc_id,
                            "valor_procedimento_na_epoca": preco
                        })
                
                if itens_para_inserir:
                    supabase.table('pacotes_itens').insert(itens_para_inserir).execute()
                
                print(f"   ✅ Itens inseridos: {len(itens_para_inserir)}")
                ui.notification_show(f"✅ Pacote '{nome}' criado!", type="message")

            # 4. Limpar e atualizar
            pacote_editando_id.set(None)
            pacote_valores_base.set({"base": 0, "final": 0, "procs": {}})
            pacotes_trigger.set(pacotes_trigger() + 1)
            # (O formulário será limpo pela recarga do pacote_form_ui)

        except Exception as e:
            print(f"❌ Erro ao salvar pacote: {e}")
            import traceback
            traceback.print_exc()
            ui.notification_show(f"❌ Erro ao salvar: {str(e)}", type="error")


    @output
    @render.ui
    def lista_pacotes_clinica():
        """Exibe a lista de pacotes cadastrados pela clínica."""
        pacotes_trigger() # Depende do trigger
        
        try:
            user = user_data()
            if not user or not supabase:
                return ui.div()

            clinica_result = supabase.table('clinicas').select('id').eq('usuario_id', user['id']).maybe_single().execute()
            if not clinica_result.data:
                return ui.div()
            
            clinica_id = clinica_result.data['id']

            # Busca pacotes com seus itens
            pacotes_res = supabase.table('pacotes').select(
                '*, pacotes_itens(procedimentos(nome))'
            ).eq('clinica_id', clinica_id).order('criado_em', desc=True).execute()

            if not pacotes_res.data:
                return ui.div(
                    {"style": "text-align: center; padding: 3rem; color: #94a3b8;"},
                    ui.h5("📭 Nenhum pacote cadastrado"),
                    ui.p("Os pacotes que você criar aparecerão aqui.")
                )

            cards = []
            for pacote in pacotes_res.data:
                ativo = pacote.get('ativo', True)
                cor_border = "#10b981" if ativo else "#ef4444"
                
                # Lista de nomes dos procedimentos
                itens = pacote.get('pacotes_itens', [])
                nomes_procs = [item.get('procedimentos', {}).get('nome', 'N/A') for item in itens]
                
                card = ui.div(
                    {"class": "card-custom", "style": f"margin-bottom: 1rem; border-left: 4px solid {cor_border};"},
                    ui.row(
                        ui.column(8,
                            ui.h6(pacote.get('nome', 'N/A'), style="margin: 0 0 0.5rem 0;"),
                            ui.p(
                                f"💰 {formatar_moeda(pacote.get('valor_final', 0))}", 
                                style="margin: 0.25rem 0; font-size: 1.1rem; font-weight: 700; color: #1DD1A1;"
                            ),
                            ui.p(
                                f"(Base: {formatar_moeda(pacote.get('valor_base', 0))} - Desc: {formatar_moeda(pacote.get('valor_desconto', 0))})",
                                style="margin: 0.25rem 0; font-size: 0.85rem; color: #546E7A;"
                            ),
                            ui.p(
                                f"📋 Inclui: {', '.join(nomes_procs) if nomes_procs else 'Nenhum'}",
                                style="margin: 0.5rem 0 0 0; font-size: 0.85rem; color: #546E7A; font-style: italic;"
                            )
                        ),
                        ui.column(4,
                            ui.div(
                                {"style": "text-align: right; display: flex; flex-direction: column; gap: 0.5rem;"},
                                ui.tags.button(
                                    "✏️ Editar",
                                    class_="btn btn-primary w-100",
                                    onclick=f"Shiny.setInputValue('editar_pacote_id', '{pacote['id']}', {{priority: 'event'}})",
                                    style="font-weight: 600; padding: 0.5rem; font-size: 0.9rem;"
                                ),
                                ui.tags.button(
                                    "🔄 Ativar" if not ativo else "⏸️ Desativar",
                                    class_=f"btn {'btn-success' if not ativo else 'btn-warning'} w-100",
                                    onclick=f"Shiny.setInputValue('toggle_pacote_id', '{pacote['id']}', {{priority: 'event'}})",
                                    style="font-weight: 600; padding: 0.5rem; font-size: 0.9rem;"
                                )
                            )
                        )
                    )
                )
                cards.append(card)
            
            return ui.div(*cards)

        except Exception as e:
            print(f"❌ Erro em lista_pacotes_clinica: {e}")
            return ui.div({"class": "alert alert-danger"}, f"Erro ao listar pacotes: {e}")

    @reactive.Effect
    def _monitor_editar_pacote():
        """Carrega os dados de um pacote para edição."""
        try:
            pacote_id = input.editar_pacote_id()
            if not pacote_id:
                return

            print(f"✏️ Carregando pacote para edição: {pacote_id}")
            pacote_editando_id.set(pacote_id)
            # A UI `pacote_form_ui` será recarregada automaticamente
            # O Effect `_calcular_valores_pacote` também será acionado quando o selectize for preenchido
            
            ui.notification_show("Carregando dados do pacote para edição...", type="message")

        except Exception as e:
            print(f"❌ Erro ao monitorar edição de pacote: {e}")

    @reactive.Effect
    def _monitor_toggle_pacote():
        """Ativa ou desativa um pacote."""
        try:
            pacote_id = input.toggle_pacote_id()
            if not pacote_id:
                return

            print(f"🔄 Toggling pacote ID: {pacote_id}")

            # Busca status atual
            result = supabase.table('pacotes').select('ativo, nome').eq('id', pacote_id).maybe_single().execute()
            if not result.data:
                return

            pacote = result.data
            novo_status = not pacote.get('ativo', True)

            # Atualiza
            supabase.table('pacotes').update({'ativo': novo_status}).eq('id', pacote_id).execute()

            # Força atualização da lista
            pacotes_trigger.set(pacotes_trigger() + 1)
            
            status_texto = "✅ Ativado" if novo_status else "⏸️ Desativado"
            ui.notification_show(f"{status_texto}: {pacote['nome']}", type="message", duration=3)

        except Exception as e:
            print(f"❌ Erro ao dar toggle no pacote: {e}")
            ui.notification_show(f"❌ Erro: {str(e)}", type="error")



    @reactive.Effect
    @reactive.event(input.btn_enviar_whatsapp)
    def handle_enviar_whatsapp():
        try:
            print("\n" + "="*60)
            print("📱 ENVIO WHATSAPP - DEBUG")
            print("="*60)
            
            venda_gerada = ultima_venda_pdf()
            whatsapp_number_raw = input.whatsapp_cliente_venda()

            # 1. Validações
            if not venda_gerada:
                ui.notification_show("⚠️ Finalize uma venda primeiro.", type="warning")
                print("❌ Nenhuma venda gerada")
                return

            if not whatsapp_number_raw:
                ui.notification_show("⚠️ Insira o número do WhatsApp.", type="warning")
                print("❌ Número não informado")
                return
                
            whatsapp_number = "".join(filter(str.isdigit, whatsapp_number_raw))
            print(f"📞 Número original: {whatsapp_number_raw}")
            print(f"📞 Número limpo: {whatsapp_number}")
            
            if len(whatsapp_number) < 10:
                ui.notification_show(
                    "⚠️ Número inválido. Use formato: 5527999998888\n"
                    "(Código país + DDD + número)",
                    type="warning",
                    duration=8
                )
                print(f"❌ Número muito curto: {len(whatsapp_number)} dígitos")
                return

            # 2. Busca dados completos da venda no banco
            venda_id = venda_gerada.get('venda_id')
            if not venda_id or not supabase:
                ui.notification_show("❌ Erro ao buscar dados da venda", type="error")
                return
            
            # Busca venda com dados da clínica e cliente
            result = supabase.table('vendas').select(
                '*, clinicas(*), clientes(*)'
            ).eq('id', venda_id).execute()
            
            if not result.data:
                ui.notification_show("❌ Venda não encontrada no banco", type="error")
                return
            
            venda_completa = result.data[0]
            clinica = venda_completa.get('clinicas', {})
            cliente = venda_completa.get('clientes', {})
            
            # 3. Coleta dados
            codigo_venda = venda_completa.get('numero_venda', 'N/A')
            cliente_nome = cliente.get('nome_completo', 'Cliente')
            
            # Dados da clínica
            clinica_nome = clinica.get('nome_fantasia') or clinica.get('razao_social', 'N/A')
            clinica_endereco = clinica.get('endereco_rua', '')
            clinica_cidade = clinica.get('endereco_cidade', '')
            clinica_estado = clinica.get('endereco_estado', '')
            clinica_telefone = clinica.get('telefone', '')
            clinica_whatsapp = clinica.get('whatsapp', '')
            
            # Formata endereço completo
            endereco_completo = f"{clinica_endereco}, {clinica_cidade}/{clinica_estado}".strip(", ")
            if not clinica_endereco:
                endereco_completo = f"{clinica_cidade}/{clinica_estado}" if clinica_cidade else "Consulte a clínica"
            
            # Procedimentos
            itens = venda_gerada.get('itens', [])
            
            print(f"📄 Código: {codigo_venda}")
            print(f"👤 Cliente: {cliente_nome}")
            print(f"🏥 Clínica: {clinica_nome}")
            print(f"📋 Itens: {len(itens)}")

            # 4. Monta mensagem MELHORADA com emojis e formatação WhatsApp
            procedimentos_lista = []
            for idx, item in enumerate(itens, 1):
                nome = item.get('nome', 'Procedimento')
                qtd = item.get('quantidade', 1)
                procedimentos_lista.append(f"{idx}. {nome} _(Qtd: {qtd})_")
            
            # Mensagem formatada para WhatsApp
            # *texto* = negrito, _texto_ = itálico, emojis nativos
            mensagem = (
                f"🎉 *Olá, {cliente_nome.split()[0]}!*\n\n"
                f"Seu atendimento foi confirmado com sucesso na *{clinica_nome}*!\n"
                f"Você deve entrar em contato com a clínica para agendamento!\n\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"📋 *CÓDIGO PARA ATENDIMENTO*\n"
                f"*{codigo_venda}*\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
                f"🏥 *DADOS DA CLÍNICA*\n"
                f"• Nome: {clinica_nome}\n"
                f"• Endereço: {endereco_completo}\n"
            )
            
            # Adiciona telefone se disponível
            if clinica_whatsapp:
                mensagem += f"• WhatsApp: {formatar_whatsapp(clinica_whatsapp)}\n"
            elif clinica_telefone:
                mensagem += f"• Telefone: {formatar_whatsapp(clinica_telefone)}\n"
            
            mensagem += (
                f"\n🔬 *PROCEDIMENTOS ADQUIRIDOS*\n"
                f"{chr(10).join(procedimentos_lista)}\n\n"
                f"⚠️ *IMPORTANTE:*\n"
                f"• Guarde este código\n"
                f"• Apresente na recepção da clínica\n"
                f"• Leve documento com foto\n\n"
                f"✅ Qualquer dúvida, entre em contato com a clínica!\n\n"
                f"_Mensagem enviada via MedPIX_"
            )

            print(f"\n📝 Mensagem gerada:")
            print(mensagem)
            print()

            # 5. Formata URL
            texto_formatado = urllib.parse.quote(mensagem, safe='')
            url = f"https://wa.me/{whatsapp_number}?text={texto_formatado}"
            
            print(f"🔗 URL gerada (primeiros 100 chars):")
            print(f"   {url[:100]}...\n")

            # 6. JavaScript com debug
            javascript_code = f"""
            console.log("");
            console.log("{'='*60}");
            console.log("📱 ENVIO WHATSAPP - DEBUG JAVASCRIPT");
            console.log("{'='*60}");
            console.log("1️⃣ Iniciando processo...");
            console.log("2️⃣ Número: {whatsapp_number}");
            console.log("3️⃣ Código: {codigo_venda}");
            console.log("4️⃣ Clínica: {clinica_nome}");
            console.log("");
            
            console.log("5️⃣ Tentando abrir WhatsApp...");
            
            try {{
                var novaAba = window.open('{url}', '_blank');
                
                if (novaAba) {{
                    console.log("✅ SUCESSO! Nova aba aberta!");
                }} else {{
                    console.log("❌ FALHA! Bloqueador de pop-ups detectado!");
                    
                    alert(
                        "⚠️ SEU NAVEGADOR BLOQUEOU O POP-UP\\n\\n" +
                        "Para enviar pelo WhatsApp:\\n" +
                        "1. Clique no ícone de 'bloqueio' na barra de endereço\\n" +
                        "2. Permita pop-ups para este site\\n" +
                        "3. Tente novamente\\n\\n" +
                        "OU use o botão verde abaixo como alternativa!"
                    );
                }}
            }} catch (error) {{
                console.error("❌ ERRO CRÍTICO:", error);
                alert("❌ Erro ao abrir WhatsApp: " + error.message);
            }}
            
            console.log("6️⃣ Script finalizado!");
            console.log("{'='*60}");
            console.log("");
            """

            ui.remove_ui(selector="#whatsapp_script_tag")
            ui.insert_ui(
                selector="#whatsapp_trigger_div",
                where="beforeEnd",
                ui=ui.tags.script(javascript_code, id="whatsapp_script_tag")
            )

            print("7️⃣ Script JavaScript injetado!")
            print("="*60 + "\n")

            ui.notification_show(
                "📱 Abrindo WhatsApp...\n"
                "Se não abrir, use o botão verde abaixo!",
                type="message",
                duration=5
            )

        except Exception as e:
            print(f"\n❌ ERRO CRÍTICO:")
            print(f"   Tipo: {type(e).__name__}")
            print(f"   Mensagem: {str(e)}")
            import traceback
            traceback.print_exc()
            print("="*60 + "\n")
            
            ui.notification_show(f"❌ Erro: {str(e)}", type="error")


    @output
    @render.ui
    def whatsapp_link_dinamico():
        """Mostra link clicável do WhatsApp (backup se pop-up for bloqueado)"""
        try:
            # Só mostra se tiver uma venda finalizada
            venda_pdf = ultima_venda_pdf()
            if not venda_pdf:
                return ui.div()
            
            # Pega o número digitado
            whatsapp_number_raw = input.whatsapp_cliente_venda()
            if not whatsapp_number_raw:
                return ui.div()
            
            # Limpa o número
            whatsapp_number = "".join(filter(str.isdigit, whatsapp_number_raw))
            if len(whatsapp_number) < 10:
                return ui.div()
            
            # Busca dados completos da venda
            venda_id = venda_pdf.get('venda_id')
            if not venda_id or not supabase:
                return ui.div()
            
            result = supabase.table('vendas').select(
                '*, clinicas(*), clientes(*)'
            ).eq('id', venda_id).execute()
            
            if not result.data:
                return ui.div()
            
            venda_completa = result.data[0]
            clinica = venda_completa.get('clinicas', {})
            cliente = venda_completa.get('clientes', {})
            
            # Coleta dados
            codigo_venda = venda_completa.get('numero_venda', 'N/A')
            cliente_nome = cliente.get('nome_completo', 'Cliente')
            clinica_nome = clinica.get('nome_fantasia') or clinica.get('razao_social', 'N/A')
            clinica_endereco = clinica.get('endereco_rua', '')
            clinica_cidade = clinica.get('endereco_cidade', '')
            clinica_estado = clinica.get('endereco_estado', '')
            clinica_whatsapp = clinica.get('whatsapp', '')
            clinica_telefone = clinica.get('telefone', '')
            
            endereco_completo = f"{clinica_endereco}, {clinica_cidade}/{clinica_estado}".strip(", ")
            if not clinica_endereco:
                endereco_completo = f"{clinica_cidade}/{clinica_estado}" if clinica_cidade else "Consulte a clínica"
            
            itens = venda_pdf.get('itens', [])
            
            # Monta mensagem (MESMA da função anterior)
            procedimentos_lista = []
            for idx, item in enumerate(itens, 1):
                nome = item.get('nome', 'Procedimento')
                qtd = item.get('quantidade', 1)
                procedimentos_lista.append(f"{idx}. {nome} _(Qtd: {qtd})_")
            
            mensagem = (
                f"🎉 *Olá, {cliente_nome.split()[0]}!*\n\n"
                f"Seu atendimento foi agendado com sucesso na *{clinica_nome}*!\n\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"📋 *CÓDIGO DA VENDA*\n"
                f"*{codigo_venda}*\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
                f"🏥 *DADOS DA CLÍNICA*\n"
                f"• Nome: {clinica_nome}\n"
                f"• Endereço: {endereco_completo}\n"
            )
            
            if clinica_whatsapp:
                mensagem += f"• WhatsApp: {formatar_whatsapp(clinica_whatsapp)}\n"
            elif clinica_telefone:
                mensagem += f"• Telefone: {formatar_whatsapp(clinica_telefone)}\n"
            
            mensagem += (
                f"\n🔬 *PROCEDIMENTOS ADQUIRIDOS*\n"
                f"{chr(10).join(procedimentos_lista)}\n\n"
                f"⚠️ *IMPORTANTE:*\n"
                f"• Guarde este código\n"
                f"• Apresente na recepção da clínica\n"
                f"• Leve documento com foto\n\n"
                f"✅ Qualquer dúvida, entre em contato com a clínica!\n\n"
                f"_Mensagem enviada via MedPIX_"
            )
            
            # Gera URL
            texto_formatado = urllib.parse.quote(mensagem, safe='')
            url = f"https://wa.me/{whatsapp_number}?text={texto_formatado}"
            
            # Retorna card com link
            return ui.div(
                {"class": "mt-3 p-3", 
                 "style": "background: linear-gradient(135deg, #25D366, #128C7E); border-radius: 0.5rem; box-shadow: 0 4px 6px rgba(0,0,0,0.1);"},
                ui.row(
                    ui.column(12,
                        ui.h6("📱 Link Alternativo do WhatsApp", 
                              style="color: white; margin: 0 0 1rem 0; text-align: center;"),
                        ui.tags.a(
                            "💬 Abrir no WhatsApp",
                            href=url,
                            target="_blank",
                            class_="btn btn-light w-100",
                            style="font-weight: 600; padding: 0.75rem; font-size: 1rem;"
                        ),
                        ui.p("👆 Use este botão se a janela não abrir automaticamente",
                             style="margin: 0.75rem 0 0 0; font-size: 0.85rem; color: white; opacity: 0.9; text-align: center;")
                    )
                )
            )
            
        except Exception as e:
            print(f"Erro em whatsapp_link_dinamico: {e}")
            return ui.div()



    # Adicione este output para o link alternativo
    @output
    @render.ui
    def whatsapp_link_alternativo():
        url = whatsapp_url()
        if not url:
            return ui.div()
        
        return ui.div(
            {"class": "mt-3 p-3", 
             "style": "background: linear-gradient(135deg, #25D366, #128C7E); border-radius: 0.5rem; box-shadow: 0 4px 6px rgba(0,0,0,0.1);"},
            ui.h6("📱 Link do WhatsApp Gerado!", 
                  style="color: white; margin: 0 0 1rem 0; text-align: center;"),
            ui.tags.a(
                "💬 Abrir no WhatsApp",
                href=url,
                target="_blank",
                class_="btn btn-light w-100",
                style="font-weight: 600; padding: 0.75rem; font-size: 1rem;"
            ),
            ui.p("Clique no botão acima se a janela não abrir automaticamente",
                 style="margin: 0.5rem 0 0 0; font-size: 0.85rem; color: white; opacity: 0.9; text-align: center;")
        )
        

    # ========== ESTATÍSTICAS DE ATENDIMENTOS ==========
    @output
    @render.text
    def stat_atendimentos_realizados():
        """Conta total de atendimentos realizados pela clínica"""
        try:
            user = user_data()
            if not user or not supabase:
                return "0"
            
            # Busca clínica
            clinica_result = supabase.table('clinicas').select('id').eq('usuario_id', user['id']).execute()
            if not clinica_result.data:
                return "0"
            
            clinica_id = clinica_result.data[0]['id']
            
            # Busca vendas da clínica
            vendas_result = supabase.table('vendas').select('id').eq('clinica_id', clinica_id).execute()
            
            if not vendas_result.data:
                return "0"
            
            vendas_ids = [v['id'] for v in vendas_result.data]
            
            # Conta atendimentos realizados
            total_atendimentos = 0
            for venda_id in vendas_ids:
                itens_result = supabase.table('itens_venda').select(
                    'id', count='exact'
                ).eq('venda_id', venda_id).eq('atendido', True).execute()
                
                total_atendimentos += (itens_result.count or 0)
            
            return str(total_atendimentos)
            
        except Exception as e:
            print(f"Erro stat_atendimentos_realizados: {e}")
            return "0"

    @output
    @render.text
    def stat_valor_total_atendimentos():
        try:
            user = user_data()
            if not user or not supabase:
                return "R$ 0,00"
            
            clinica_result = supabase.table('clinicas').select('id').eq('usuario_id', user['id']).execute()
            if not clinica_result.data:
                return "R$ 0,00"
            
            clinica_id = clinica_result.data[0]['id']
            
            # Busca itens atendidos
            result = supabase.table('itens_venda').select(
                'preco_total, venda_id'
            ).eq('atendido', True).execute()
            
            if not result.data:
                return "R$ 0,00"
            
            # Filtra apenas desta clínica
            vendas_clinica = supabase.table('vendas').select('id').eq('clinica_id', clinica_id).execute()
            vendas_ids = [v['id'] for v in vendas_clinica.data] if vendas_clinica.data else []
            
            total = sum([
                float(item.get('preco_total', 0) or 0) 
                for item in result.data 
                if item.get('venda_id') in vendas_ids
            ])
            
            return formatar_moeda(total)
        except:
            return "R$ 0,00"

    @output
    @render.text
    def stat_comissao_total():
        try:
            user = user_data()
            if not user or not supabase:
                return "R$ 0,00"
            
            clinica_result = supabase.table('clinicas').select('id').eq('usuario_id', user['id']).execute()
            if not clinica_result.data:
                return "R$ 0,00"
            
            clinica_id = clinica_result.data[0]['id']
            
            # Busca comissão configurada
            comissao_result = supabase.table('comissoes_clinica').select('*').eq('clinica_id', clinica_id).execute()
            
            if not comissao_result.data:
                return "R$ 0,00"
            
            comissao_config = comissao_result.data[0]
            
            # Busca itens atendidos
            result = supabase.table('itens_venda').select('preco_total, venda_id').eq('atendido', True).execute()
            
            if not result.data:
                return "R$ 0,00"
            
            vendas_clinica = supabase.table('vendas').select('id').eq('clinica_id', clinica_id).execute()
            vendas_ids = [v['id'] for v in vendas_clinica.data] if vendas_clinica.data else []
            
            total = sum([
                float(item.get('preco_total', 0) or 0) 
                for item in result.data 
                if item.get('venda_id') in vendas_ids
            ])
            
            # Calcula comissão
            if comissao_config.get('tipo') == 'percentual':
                comissao = total * (comissao_config.get('valor_percentual', 0) / 100)
            else:
                # Conta quantas vendas
                vendas_count = len(set([item['venda_id'] for item in result.data if item.get('venda_id') in vendas_ids]))
                comissao = vendas_count * comissao_config.get('valor_fixo', 0)
            
            return formatar_moeda(comissao)
        except:
            return "R$ 0,00"

    @output
    @render.text
    def stat_pagamentos_recebidos():
        """Calcula o total de pagamentos recebidos pela clínica (parcelas pagas)"""
        try:
            user = user_data()
            if not user or not supabase:
                return "R$ 0,00"
            
            clinica_result = supabase.table('clinicas').select('id').eq('usuario_id', user['id']).execute()
            if not clinica_result.data:
                return "R$ 0,00"
            
            clinica_id = clinica_result.data[0]['id']
            
            # Busca comissão configurada
            comissao_result = supabase.table('comissoes_clinica').select('*').eq('clinica_id', clinica_id).execute()
            
            if not comissao_result.data:
                return "R$ 0,00"
            
            comissao_config = comissao_result.data[0]
            
            # Busca todas as vendas da clínica com pagamento confirmado
            vendas_result = supabase.table('vendas').select('*').eq(
                'clinica_id', clinica_id
            ).eq('pagamento_confirmado', True).execute()
            
            if not vendas_result.data:
                return "R$ 0,00"
            
            total_recebido = 0
            
            for venda in vendas_result.data:
                valor_venda = float(venda.get('valor_total', 0) or 0)
                
                # Calcula comissão
                if comissao_config.get('tipo') == 'percentual':
                    percentual = float(comissao_config.get('valor_percentual', 0))
                    comissao = valor_venda * (percentual / 100)
                else:
                    comissao = float(comissao_config.get('valor_fixo', 0))
                
                valor_liquido = valor_venda - comissao
                valor_parcela = valor_liquido / 2
                
                # Soma parcelas já pagas
                if venda.get('parcela1_clinica_paga', False):
                    total_recebido += valor_parcela
                
                if venda.get('parcela2_clinica_paga', False):
                    total_recebido += valor_parcela
            
            return formatar_moeda(total_recebido)
            
        except Exception as e:
            print(f"Erro stat_pagamentos_recebidos: {e}")
            return "R$ 0,00"

    @output
    @render.text
    def stat_valor_receber():
        """Calcula o valor pendente (ainda não pago) para a clínica"""
        try:
            user = user_data()
            if not user or not supabase:
                return "R$ 0,00"
            
            clinica_result = supabase.table('clinicas').select('id').eq('usuario_id', user['id']).execute()
            if not clinica_result.data:
                return "R$ 0,00"
            
            clinica_id = clinica_result.data[0]['id']
            
            # Busca comissão configurada
            comissao_result = supabase.table('comissoes_clinica').select('*').eq('clinica_id', clinica_id).execute()
            
            if not comissao_result.data:
                return "R$ 0,00"
            
            comissao_config = comissao_result.data[0]
            
            # Busca todas as vendas da clínica com pagamento confirmado
            vendas_result = supabase.table('vendas').select('*').eq(
                'clinica_id', clinica_id
            ).eq('pagamento_confirmado', True).execute()
            
            if not vendas_result.data:
                return "R$ 0,00"
            
            total_a_receber = 0
            
            for venda in vendas_result.data:
                valor_venda = float(venda.get('valor_total', 0) or 0)
                
                # Calcula comissão
                if comissao_config.get('tipo') == 'percentual':
                    percentual = float(comissao_config.get('valor_percentual', 0))
                    comissao = valor_venda * (percentual / 100)
                else:
                    comissao = float(comissao_config.get('valor_fixo', 0))
                
                valor_liquido = valor_venda - comissao
                valor_parcela = valor_liquido / 2
                
                # Soma apenas parcelas PENDENTES
                if not venda.get('parcela1_clinica_paga', False):
                    total_a_receber += valor_parcela
                
                # Parcela 2: verifica se todos itens foram atendidos
                itens = venda.get('itens_venda', []) if 'itens_venda' in venda else []
                if not itens:
                    # Busca itens se não vieram no select
                    itens_result = supabase.table('itens_venda').select('*').eq('venda_id', venda['id']).execute()
                    itens = itens_result.data if itens_result.data else []
                
                if itens:
                    itens_atendidos = [item for item in itens if item.get('atendido')]
                    todos_atendidos = len(itens_atendidos) == len(itens)
                    
                    if todos_atendidos and not venda.get('parcela2_clinica_paga', False):
                        total_a_receber += valor_parcela
            
            return formatar_moeda(total_a_receber)
            
        except Exception as e:
            print(f"Erro stat_valor_receber: {e}")
            import traceback
            traceback.print_exc()
            return "R$ 0,00"
            
            
    @output
    @render.ui
    def lista_atendimentos_realizados():
        try:
            user = user_data()
            if not user or not supabase:
                return ui.div()
            
            # Busca clínica
            clinica_result = supabase.table('clinicas').select('id').eq('usuario_id', user['id']).execute()
            if not clinica_result.data:
                return ui.div(
                    {"style": "text-align: center; padding: 3rem; color: #94a3b8;"},
                    ui.h5("❌ Clínica não encontrada")
                )
            
            clinica_id = clinica_result.data[0]['id']
            
            # Busca vendas da clínica com pagamento confirmado
            result = supabase.table('vendas').select(
                '*, clientes(nome_completo, cpf), itens_venda(*)'
            ).eq('clinica_id', clinica_id).eq('pagamento_confirmado', True).order('criado_em', desc=True).execute()
            
            if not result.data:
                return ui.div(
                    {"style": "text-align: center; padding: 3rem; color: #94a3b8;"},
                    ui.h5("📭 Nenhum atendimento encontrado"),
                    ui.p("Os atendimentos realizados aparecerão aqui")
                )
            
            # Busca comissão da clínica
            comissao_result = supabase.table('comissoes_clinica').select('*').eq('clinica_id', clinica_id).execute()
            comissao_config = comissao_result.data[0] if comissao_result.data else {}
            
            # Aplica filtros
            filtro = input.filtro_status_atendimento()
            busca = input.buscar_atendimento()
            
            cards = []
            for venda in result.data:
                # Filtra por busca
                if busca:
                    numero = venda.get('numero_venda', '')
                    cliente_nome = venda.get('clientes', {}).get('nome_completo', '')
                    if busca.lower() not in numero.lower() and busca.lower() not in cliente_nome.lower():
                        continue
                
                # Calcula valores
                valor_venda = float(venda.get('valor_total', 0) or 0)
                
                # Calcula comissão
                if comissao_config.get('tipo') == 'percentual':
                    percentual = float(comissao_config.get('valor_percentual', 0))
                    comissao = valor_venda * (percentual / 100)
                else:
                    comissao = float(comissao_config.get('valor_fixo', 0))
                
                valor_liquido = valor_venda - comissao
                valor_parcela = valor_liquido / 2
                
                # Status das parcelas
                parcela1_paga = venda.get('parcela1_clinica_paga', False)
                parcela2_paga = venda.get('parcela2_clinica_paga', False)
                data_parcela1 = venda.get('data_pagamento_parcela1_clinica')
                data_parcela2 = venda.get('data_pagamento_parcela2_clinica')
                
                # Verifica se todos itens foram atendidos
                itens = venda.get('itens_venda', [])
                itens_atendidos = [item for item in itens if item.get('atendido')]
                todos_atendidos = len(itens) > 0 and len(itens_atendidos) == len(itens)
                
                # Aplica filtro de status
                if filtro == "pendente" and parcela1_paga and parcela2_paga:
                    continue
                elif filtro == "pago" and not (parcela1_paga and parcela2_paga):
                    continue
                
                # Define cor e status
                if parcela1_paga and parcela2_paga:
                    cor_border = "#10b981"
                    status_principal = "✅ Totalmente Pago"
                elif parcela1_paga or parcela2_paga:
                    cor_border = "#f59e0b"
                    status_principal = "🟡 Parcialmente Pago"
                else:
                    cor_border = "#ef4444"
                    status_principal = "⏳ Aguardando Pagamento"
                
                cliente_nome = venda.get('clientes', {}).get('nome_completo', 'N/A')
                
                card = ui.div(
                    {"class": "card-custom", "style": f"margin-bottom: 1rem; border-left: 4px solid {cor_border};"},
                    ui.row(
                        ui.column(8,
                            ui.h6(f"📄 {venda['numero_venda']}", style="margin: 0 0 0.5rem 0;"),
                            ui.p(f"👤 Cliente: {cliente_nome}", style="margin: 0.25rem 0; font-size: 0.9rem;"),
                            ui.p(f"💰 Valor Total: {formatar_moeda(valor_venda)}", 
                                 style="margin: 0.25rem 0; font-size: 0.9rem; font-weight: 600; color: #1DD1A1;"),
                            ui.p(f"💳 Comissão (12%): -{formatar_moeda(comissao)}", 
                                 style="margin: 0.25rem 0; font-size: 0.9rem; color: #f59e0b;"),
                            ui.p(f"💵 Valor Líquido: {formatar_moeda(valor_liquido)}", 
                                 style="margin: 0.25rem 0; font-size: 1rem; font-weight: 700; color: #10b981;"),
                            ui.hr(style="margin: 0.5rem 0;"),
                            ui.p(f"📦 Parcela 1 (50%): {formatar_moeda(valor_parcela)} - {'✅ Pago' if parcela1_paga else '⏳ Pendente'}", 
                                 style=f"margin: 0.25rem 0; font-size: 0.9rem; color: {'#10b981' if parcela1_paga else '#f59e0b'};"),
                            ui.p(f"   📅 {pd.to_datetime(data_parcela1).strftime('%d/%m/%Y %H:%M') if data_parcela1 else '-'}", 
                                 style="margin: 0 0 0 1rem; font-size: 0.8rem; color: #546E7A;") if parcela1_paga else ui.div(),
                            ui.p(f"📦 Parcela 2 (50%): {formatar_moeda(valor_parcela)} - {'✅ Pago' if parcela2_paga else ('⏳ Aguardando Atendimentos' if not todos_atendidos else '⏳ Pendente')}", 
                                 style=f"margin: 0.25rem 0; font-size: 0.9rem; color: {'#10b981' if parcela2_paga else '#94a3b8' if not todos_atendidos else '#f59e0b'};"),
                            ui.p(f"   📅 {pd.to_datetime(data_parcela2).strftime('%d/%m/%Y %H:%M') if data_parcela2 else '-'}", 
                                 style="margin: 0 0 0 1rem; font-size: 0.8rem; color: #546E7A;") if parcela2_paga else ui.div()
                        ),
                        ui.column(4,
                            ui.div(
                                {"style": "text-align: right;"},
                                ui.p(status_principal, style=f"margin: 0 0 1rem 0; font-weight: 600; font-size: 1.1rem; color: {cor_border};"),
                                ui.p(f"🩺 {len(itens_atendidos)}/{len(itens)} atendidos", 
                                     style="margin: 0; font-size: 0.9rem; color: #546E7A;")
                            )
                        )
                    )
                )
                cards.append(card)
            
            if not cards:
                return ui.div(
                    {"style": "text-align: center; padding: 3rem; color: #94a3b8;"},
                    ui.h5("📭 Nenhum atendimento com os filtros aplicados")
                )
            
            return ui.div(*cards)
            
        except Exception as e:
            print(f"Erro lista_atendimentos_realizados: {e}")
            import traceback
            traceback.print_exc()
            return ui.div(ui.p(f"Erro: {str(e)}", style="color: red;"))
            

    # ========== EFFECTS PARA PAGAMENTO DE PARCELAS (ANTES DO RENDER) ==========
    @reactive.Effect
    def _monitor_confirmar_parcela1():
        """Confirma pagamento da Parcela 1"""
        try:
            clinica_id = None
            try:
                clinica_id = input.confirmar_pagar_parcela1()
            except:
                return
            
            if not clinica_id or not supabase:
                return
            
            print(f"\n{'='*60}")
            print(f"💸 CONFIRMANDO PAGAMENTO PARCELA 1")
            print(f"{'='*60}")
            
            user = user_data()
            if not user:
                return
            
            # Busca vendas com parcela 1 pendente
            vendas_result = supabase.table('vendas').select('*').eq(
                'clinica_id', clinica_id
            ).eq('pagamento_confirmado', True).eq('parcela1_clinica_paga', False).execute()
            
            if not vendas_result.data:
                ui.notification_show("⚠️ Nenhuma parcela 1 pendente!", type="warning")
                return
            
            # Busca comissão
            comissao_result = supabase.table('comissoes_clinica').select('*').eq('clinica_id', clinica_id).execute()
            comissao_config = comissao_result.data[0] if comissao_result.data else {}
            
            total_pago = 0
            vendas_pagas = []
            
            for venda in vendas_result.data:
                valor_venda = float(venda.get('valor_total', 0) or 0)
                
                # Calcula comissão
                if comissao_config.get('tipo') == 'percentual':
                    comissao = valor_venda * (comissao_config.get('valor_percentual', 0) / 100)
                else:
                    comissao = comissao_config.get('valor_fixo', 0)
                
                valor_liquido = valor_venda - comissao
                valor_parcela1 = valor_liquido / 2
                
                # Atualiza venda
                supabase.table('vendas').update({
                    'parcela1_clinica_paga': True,
                    'data_pagamento_parcela1_clinica': datetime.now().isoformat(),
                    'superusuario_pagou_parcela1_id': user['id']
                }).eq('id', venda['id']).execute()
                
                try:
                    venda = supabase.table('vendas').select('*, clinicas(*)').eq('id', venda_id).single().execute()
                    if venda.data and venda.data.get('clinicas'):
                        clinica = venda.data['clinicas']
                        valor_parcela = venda.data['valor_total'] * 0.5
                        
                        mensagem = f"""
                🎉 *PARCELA 1 PAGA!*

                Valor: R$ {valor_parcela:.2f}
                Venda: #{venda.data.get('numero_venda')}

                O pagamento foi realizado via PIX.

                _Mensagem enviada via MedPIX_
                        """
                        
                        enviar_whatsapp(clinica.get('whatsapp'), mensagem)
                except Exception as e:
                    print(f"⚠️ Erro ao notificar clínica: {e}")
                
                total_pago += valor_parcela1
                vendas_pagas.append(venda['numero_venda'])
            
            print(f"✅ {len(vendas_pagas)} parcelas pagas!")
            print(f"💰 Total: {formatar_moeda(total_pago)}")
            print(f"{'='*60}\n")
            
            ui.notification_show(
                f"✅ Parcela 1 paga com sucesso!\n"
                f"📄 Vendas: {len(vendas_pagas)}\n"
                f"💰 Total: {formatar_moeda(total_pago)}",
                type="message",
                duration=8
            )
            
        except Exception as e:
            print(f"❌ Erro em _monitor_confirmar_parcela1: {e}")
            import traceback
            traceback.print_exc()
            ui.notification_show(f"❌ Erro: {str(e)}", type="error")


    @reactive.Effect
    def _monitor_confirmar_parcela2():
        """Confirma pagamento da Parcela 2"""
        try:
            clinica_id = None
            try:
                clinica_id = input.confirmar_pagar_parcela2()
            except:
                return
            
            if not clinica_id or not supabase:
                return
            
            print(f"\n{'='*60}")
            print(f"💸 CONFIRMANDO PAGAMENTO PARCELA 2")
            print(f"{'='*60}")
            
            user = user_data()
            if not user:
                return
            
            # Busca vendas com parcela 2 pendente E todos atendimentos concluídos
            vendas_result = supabase.table('vendas').select(
                '*, itens_venda(*)'
            ).eq('clinica_id', clinica_id).eq('pagamento_confirmado', True).eq(
                'parcela2_clinica_paga', False
            ).execute()
            
            if not vendas_result.data:
                ui.notification_show("⚠️ Nenhuma parcela 2 pendente!", type="warning")
                return
            
            # Busca comissão
            comissao_result = supabase.table('comissoes_clinica').select('*').eq('clinica_id', clinica_id).execute()
            comissao_config = comissao_result.data[0] if comissao_result.data else {}
            
            total_pago = 0
            vendas_pagas = []
            
            for venda in vendas_result.data:
                # Verifica se TODOS os itens foram atendidos
                itens = venda.get('itens_venda', [])
                if not itens:
                    continue
                
                itens_atendidos = [item for item in itens if item.get('atendido')]
                
                if len(itens_atendidos) != len(itens):
                    continue  # Pula se não estiver completo
                
                valor_venda = float(venda.get('valor_total', 0) or 0)
                
                # Calcula comissão
                if comissao_config.get('tipo') == 'percentual':
                    comissao = valor_venda * (comissao_config.get('valor_percentual', 0) / 100)
                else:
                    comissao = comissao_config.get('valor_fixo', 0)
                
                valor_liquido = valor_venda - comissao
                valor_parcela2 = valor_liquido / 2
                
                # Atualiza venda
                supabase.table('vendas').update({
                    'parcela2_clinica_paga': True,
                    'data_pagamento_parcela2_clinica': datetime.now().isoformat(),
                    'superusuario_pagou_parcela2_id': user['id']
                }).eq('id', venda['id']).execute()
                
                total_pago += valor_parcela2
                vendas_pagas.append(venda['numero_venda'])
            
            if not vendas_pagas:
                ui.notification_show("⚠️ Nenhuma venda com todos os atendimentos concluídos!", type="warning")
                return
            
            print(f"✅ {len(vendas_pagas)} parcelas pagas!")
            print(f"💰 Total: {formatar_moeda(total_pago)}")
            print(f"{'='*60}\n")
            
            ui.notification_show(
                f"✅ Parcela 2 paga com sucesso!\n"
                f"📄 Vendas: {len(vendas_pagas)}\n"
                f"💰 Total: {formatar_moeda(total_pago)}",
                type="message",
                duration=8
            )
            
        except Exception as e:
            print(f"❌ Erro em _monitor_confirmar_parcela2: {e}")
            import traceback
            traceback.print_exc()
            ui.notification_show(f"❌ Erro: {str(e)}", type="error")

            
    @output
    @render.text
    def stat_clinicas_pendentes():
        try:
            if not supabase:
                return "0"
            
            # Busca vendas com parcelas pendentes
            result = supabase.table('vendas').select(
                'clinica_id'
            ).eq('pagamento_confirmado', True).or_(
                'parcela1_clinica_paga.eq.false,parcela2_clinica_paga.eq.false'
            ).execute()
            
            if not result.data:
                return "0"
            
            clinicas_pendentes = set([v['clinica_id'] for v in result.data if v.get('clinica_id')])
            return str(len(clinicas_pendentes))
        except:
            return "0"

    @output
    @render.text
    def stat_total_pagar_clinicas():
        try:
            if not supabase:
                return "R$ 0,00"
            
            total_pagar = 0
            
            # Busca vendas com parcelas pendentes
            vendas_result = supabase.table('vendas').select(
                '*, itens_venda(*)'
            ).eq('pagamento_confirmado', True).execute()
            
            if not vendas_result.data:
                return "R$ 0,00"
            
            for venda in vendas_result.data:
                clinica_id = venda.get('clinica_id')
                if not clinica_id:
                    continue
                
                # Busca comissão
                comissao_result = supabase.table('comissoes_clinica').select('*').eq('clinica_id', clinica_id).execute()
                comissao_config = comissao_result.data[0] if comissao_result.data else {}
                
                # Calcula valor da venda
                itens_atendidos = [item for item in venda.get('itens_venda', []) if item.get('atendido')]
                if itens_atendidos:
                    valor_venda = sum([float(item.get('preco_total', 0) or 0) for item in itens_atendidos])
                else:
                    valor_venda = float(venda.get('valor_total', 0) or 0)
                
                # Calcula comissão
                if comissao_config.get('tipo') == 'percentual':
                    comissao = valor_venda * (comissao_config.get('valor_percentual', 0) / 100)
                else:
                    comissao = comissao_config.get('valor_fixo', 0)
                
                valor_liquido = valor_venda - comissao
                valor_parcela = valor_liquido / 2
                
                # Soma parcelas pendentes
                if not venda.get('parcela1_clinica_paga', False):
                    total_pagar += valor_parcela
                if not venda.get('parcela2_clinica_paga', False):
                    total_pagar += valor_parcela
            
            return formatar_moeda(total_pagar)
        except:
            return "R$ 0,00"

    @output
    @render.text
    def stat_clinicas_pagas_mes():
        try:
            if not supabase:
                return "0"
            
            primeiro_dia = date.today().replace(day=1)
            
            result = supabase.table('vendas').select(
                'clinica_id'
            ).or_(
                f'data_pagamento_parcela1_clinica.gte.{primeiro_dia}T00:00:00,data_pagamento_parcela2_clinica.gte.{primeiro_dia}T00:00:00'
            ).execute()
            
            if not result.data:
                return "0"
            
            clinicas_pagas = set([v['clinica_id'] for v in result.data if v.get('clinica_id')])
            return str(len(clinicas_pagas))
        except:
            return "0"
 
    @reactive.effect
    @reactive.event(input.mudar_aba_minhas_compras)
    def mudar_para_aba_minhas_compras():
        """Muda para a aba Minhas Compras após fechar modal PIX"""
        try:
            ui.update_navs("tabs_cliente", selected="📋 Minhas Compras")
            print("✅ Navegação automática para aba 'Minhas Compras'")
        except Exception as e:
            print(f"⚠️ Erro ao mudar de aba: {e}")   
                        
    @reactive.effect
    @reactive.event(input.venda_expirada)
    def _deletar_venda_expirada():
        """Deleta venda quando o timer expira no frontend"""
        try:
            venda_id = input.venda_expirada()
            if not venda_id or not supabase:
                return
            
            print(f"🗑️ Deletando venda expirada: {venda_id}")
            
            # Deleta itens da venda
            supabase.table('itens_venda').delete().eq('venda_id', venda_id).execute()
            
            # Deleta cashback associado
            supabase.table('cashback_pagamentos').delete().eq('venda_id', venda_id).execute()
            
            # Deleta a venda
            supabase.table('vendas').delete().eq('id', venda_id).execute()
            
            print(f"✅ Venda {venda_id} deletada com sucesso")
            
            # Atualiza a UI
            minhas_compras_trigger.set(minhas_compras_trigger() + 1)
            
            ui.notification_show(
                "⏰ Pedido expirado e cancelado automaticamente. Faça um novo pedido se desejar.",
                type="warning",
                duration=10
            )
            
        except Exception as e:
            print(f"❌ Erro ao deletar venda expirada: {e}")
            import traceback
            traceback.print_exc()
            
    # ===================================================================
    # === 📺 INÍCIO - RENDERIZAÇÃO DA PÁGINA PÚBLICA (VITRINE) ===
    # ===================================================================

    @output
    @render.ui
    def public_vitrine_page_ui():
        """Renderiza a ESTRUTURA da página pública (fundo, CSS, etc)."""
        return ui.page_fluid(
            ui.tags.head(
                ui.tags.style("""
                    body {
                        background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%);
                        font-family: 'Segoe UI', sans-serif;
                    }
                    .vitrine-container {
                        max-width: 900px;
                        margin: 2rem auto;
                        padding: 0 1rem;
                    }
                    .vitrine-header {
                        text-align: center;
                        margin-bottom: 2rem;
                    }
                    .vitrine-banner {
                        width: 100%;
                        height: 250px;
                        object-fit: cover;
                        border-radius: 1rem;
                        box-shadow: 0 8px 20px rgba(0,0,0,0.1);
                        margin-bottom: 1.5rem;
                    }
                    .vitrine-card {
                        background: white;
                        border-radius: 1rem;
                        padding: 1.5rem;
                        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
                        margin-bottom: 1rem;
                    }
                    .btn-comprar-agora {
                        display: block;
                        width: 100%;
                        max-width: 400px;
                        margin: 2rem auto;
                        padding: 1rem;
                        font-size: 1.25rem;
                        font-weight: 700;
                        text-align: center;
                        text-decoration: none;
                        background: linear-gradient(135deg, #1DD1A1, #0D9488);
                        color: white;
                        border-radius: 0.75rem;
                        transition: all 0.3s;
                    }
                    .btn-comprar-agora:hover {
                        transform: translateY(-3px);
                        box-shadow: 0 8px 16px rgba(102, 126, 234, 0.4);
                    }
                """)
            ),
            # O conteúdo real será injetado aqui
            ui.output_ui("public_vitrine_content")
        )

    @output
    @render.ui
    def public_vitrine_content():
        """Renderiza o CONTEÚDO da vitrine (dados da clínica) - MELHORADO"""
        try:
            # 1. Pega o ID da clínica pela URL
            params = get_url_params()
            clinic_id = params.get("clinic_id")
            
            if not clinic_id or not supabase:
                return ui.div(
                    {"class": "alert alert-danger", "style": "margin: 2rem auto; max-width: 600px;"},
                    "❌ Erro: Clínica não encontrada. Verifique o QR Code."
                )
            
            # 2. Busca dados da clínica
            clinica_res = supabase.table('clinicas').select('*').eq('id', clinic_id).maybe_single().execute()
            if not clinica_res.data:
                return ui.div(
                    {"class": "alert alert-danger", "style": "margin: 2rem auto; max-width: 600px;"},
                    "❌ Erro: Clínica não encontrada no sistema."
                )
            
            clinica = clinica_res.data
            
            # 3. Busca pacotes configurados para vitrine (com destaque primeiro)
            pacotes_res = supabase.table('pacotes').select('*').eq('clinica_id', clinic_id).eq('ativo', True).order('vitrine_destaque', desc=True).order('nome').execute()
            
            # 4. Busca procedimentos individuais
            procs_res = supabase.table('procedimentos').select('*').eq('clinica_id', clinic_id).eq('ativo', True).order('nome').execute()
            
            # --- Constrói Cards de Pacotes (MELHORADOS) ---
            cards_pacotes = []
            
            if pacotes_res.data:
                cards_pacotes.append(
                    ui.h3("🎁 Pacotes Promocionais", 
                          style="color: #1e40af; margin: 2rem 0 1.5rem 0; text-align: center; font-weight: 700;")
                )
                
                for pacote in pacotes_res.data:
                    preco = float(pacote.get('valor_final', 0))
                    nome = pacote.get('nome', 'Pacote')
                    descricao_original = pacote.get('descricao', '')
                    descricao_vitrine = pacote.get('vitrine_descricao', '') or descricao_original
                    imagem_url = pacote.get('vitrine_imagem_url', '')
                    destaque = pacote.get('vitrine_destaque', False)
                    
                    # Busca procedimentos inclusos
                    itens_res = supabase.table('pacotes_itens').select('procedimentos(nome)').eq('pacote_id', pacote['id']).execute()
                    procedimentos_inclusos = [item['procedimentos']['nome'] for item in itens_res.data if item.get('procedimentos')]
                    
                    # Estilo especial para destaque
                    estilo_card = "border: 3px solid #f59e0b; box-shadow: 0 12px 32px rgba(245, 158, 11, 0.3);" if destaque else "border: 1px solid #e5e7eb;"
                    
                    cards_pacotes.append(
                        ui.div(
                            {"class": "vitrine-card", "style": estilo_card},
                            
                            # Badge de destaque
                            ui.div(
                                {"style": "background: linear-gradient(135deg, #f59e0b, #d97706); color: white; padding: 0.5rem 1rem; border-radius: 0.5rem; display: inline-block; margin-bottom: 1rem; font-weight: 700; font-size: 0.85rem;"},
                                "⭐ PACOTE EM DESTAQUE"
                            ) if destaque else ui.div(),
                            
                            # Imagem do pacote
                            ui.img(
                                src=imagem_url,
                                style="width: 100%; height: 250px; object-fit: cover; border-radius: 0.75rem; margin-bottom: 1rem;"
                            ) if imagem_url else ui.div(),
                            
                            # Nome do pacote
                            ui.h4(nome, style="color: #1e293b; margin-bottom: 0.75rem; font-weight: 700;"),
                            
                            # Descrição motivacional
                            ui.p(
                                descricao_vitrine,
                                style="color: #475569; font-size: 1rem; line-height: 1.6; margin-bottom: 1rem;"
                            ),
                            
                            # Lista de procedimentos inclusos
                            ui.div(
                                {"style": "background: #f8fafc; padding: 1rem; border-radius: 0.5rem; margin-bottom: 1rem; border-left: 4px solid #3b82f6;"},
                                ui.h6("📋 Inclui:", style="color: #1e40af; margin-bottom: 0.5rem; font-weight: 600;"),
                                ui.HTML("<br>".join([f"✓ {proc}" for proc in procedimentos_inclusos]))
                            ) if procedimentos_inclusos else ui.div(),
                            
                            # Preço destacado
                            ui.div(
                                {"style": "text-align: center; padding: 1.5rem; background: linear-gradient(135deg, #ecfdf5, #d1fae5); border-radius: 0.75rem; margin-top: 1rem;"},
                                ui.p("Valor do Pacote:", style="color: #047857; font-size: 0.9rem; margin: 0;"),
                                ui.h2(formatar_moeda(preco), style="color: #10b981; margin: 0.25rem 0 0 0; font-weight: 800; font-size: 2rem;")
                            )
                        )
                    )
            
            # --- Cards de Procedimentos Individuais (OPCIONAIS) ---
            cards_procedimentos = []
            if procs_res.data:
                cards_procedimentos.append(
                    ui.h3("🔬 Procedimentos Individuais", 
                          style="color: #059669; margin: 3rem 0 1.5rem 0; text-align: center; font-weight: 700;")
                )
                
                for proc in procs_res.data:
                    preco = float(proc.get('preco', 0))
                    cards_procedimentos.append(
                        ui.div(
                            {"class": "vitrine-card", "style": "border-left: 4px solid #10b981;"},
                            ui.row(
                                ui.column(8,
                                    ui.h5(proc.get('nome'), style="color: #1e293b; margin-bottom: 0.5rem;"),
                                    ui.p(proc.get('descricao') or "", style="font-size: 0.95rem; color: #64748b;")
                                ),
                                ui.column(4,
                                    ui.h4(formatar_moeda(preco), 
                                          style="color: #10b981; text-align: right; font-weight: 700;")
                                )
                            )
                        )
                    )
            
            # --- Constrói URL de "Comprar Agora" ---
            base_url = "https://medpix.onrender.com"        
            
            # --- Renderiza a Página Completa ---
            return ui.div(
                {"class": "vitrine-container"},
                
                # === HEADER ===
                ui.div(
                    {"class": "vitrine-header"},
                    ui.img(
                        src="https://github.com/AMalta/MedPIX/blob/0e7c9ede0d9f51ca7e552b59e999047894baae79/images/logoMP.jpeg",
                        style="height: 120px; width: auto; margin-bottom: 1.5rem;"
                    ),
                    ui.h1(
                        clinica.get('vitrine_titulo') or clinica.get('nome_fantasia') or "Bem-vindo!",
                        style="color: #1e293b; margin-bottom: 1rem; font-size: 2.5rem; font-weight: 800;"
                    ),
                    ui.p(
                        clinica.get('vitrine_mensagem') or "Confira nossos exames e pacotes abaixo.",
                        style="font-size: 1.2rem; color: #475569; line-height: 1.6; max-width: 700px; margin: 0 auto;"
                    )
                ),
                
                # === BANNER ===
                ui.img(
                    src=clinica.get('vitrine_banner_url'),
                    class_="vitrine-banner"
                ) if clinica.get('vitrine_banner_url') else ui.div(),
                
                # === PACOTES ===
                *cards_pacotes,
                
                # === PROCEDIMENTOS ===
                *cards_procedimentos,
                
                # === CALL TO ACTION ===
                ui.div(
                    {"style": "text-align: center; margin: 3rem 0;"},
                    ui.a(
                        "🛒 Quero Comprar Agora!",
                        href=base_url,
                        class_="btn-comprar-agora",
                        style="display: inline-block; padding: 1.25rem 3rem; font-size: 1.3rem; background: linear-gradient(135deg, #10b981, #059669); color: white; text-decoration: none; border-radius: 0.75rem; font-weight: 700; box-shadow: 0 8px 24px rgba(16, 185, 129, 0.4); transition: all 0.3s;"
                    )
                ),
                
                # === FOOTER ===
                ui.div(
                    {"style": "text-align: center; margin-top: 4rem; padding: 2rem 0; border-top: 2px solid #e5e7eb;"},
                    ui.p(
                        f"📍 {clinica.get('endereco', '')}",
                        style="color: #64748b; margin-bottom: 0.5rem;"
                    ) if clinica.get('endereco') else ui.div(),
                    ui.p(
                        f"© {datetime.now().year} {clinica.get('nome_fantasia', 'Clínica')} • Powered by MedPIX",
                        style="color: #94a3b8; font-size: 0.85rem;"
                    )
                )
            )
        
        except Exception as e:
            print(f"❌ Erro ao renderizar vitrine: {e}")
            import traceback
            traceback.print_exc()
            return ui.div(
                {"class": "alert alert-danger", "style": "margin: 2rem auto; max-width: 600px;"},
                f"❌ Erro ao carregar página: {e}"
            )

    # ===================================================================
    # === 📺 FIM - LÓGICA DA VITRINE ===
    # ===================================================================
             
app = App(app_ui, server)
