export default function Privacy() {
  return (
    <div className="legal">
      <div className="legal-box">
        <a className="legal-back" href="/">← Voltar ao Posthink</a>
        <h1>Política de Privacidade</h1>
        <p className="legal-meta">
          Última atualização: 16 de julho de 2026 · Lei nº 13.709/2018 (LGPD)
        </p>

        <h2>1. Quem somos</h2>
        <p>
          O Posthink é operado pela <strong>Hack Tech Farm</strong>, sediada em Porto Alegre/RS,
          Brasil, controladora dos dados pessoais tratados neste serviço.
        </p>
        <p>
          Canal do encarregado (DPO) para assuntos de privacidade:{" "}
          <a href="mailto:privacidade@posthink.com.br">privacidade@posthink.com.br</a>
        </p>

        <h2>2. Quais dados coletamos</h2>
        <ul>
          <li>
            <strong>Cadastro:</strong> nome, e-mail e senha (armazenada apenas como hash
            criptográfico — não temos acesso à sua senha). Se você entrar com o Google,
            recebemos seu identificador, nome e e-mail verificado.
          </li>
          <li>
            <strong>Conta do LinkedIn:</strong> ao conectar sua conta, recebemos seu
            identificador público (URN), nome de exibição e um token de acesso. O token é
            armazenado <strong>criptografado</strong> e serve exclusivamente para publicar os
            posts que você aprovar.
          </li>
          <li>
            <strong>Conteúdo:</strong> pautas, instruções, textos gerados, imagens enviadas
            ou geradas, perfil de marca e documentos que você anexar como referência.
          </li>
          <li>
            <strong>Pagamento:</strong> processado pela Stripe. Guardamos apenas um
            identificador de cliente e o status do plano —{" "}
            <strong>nunca recebemos ou armazenamos dados do seu cartão</strong>.
          </li>
          <li>
            <strong>Registros técnicos:</strong> logs de publicação (data, resultado e
            resposta do LinkedIn) para auditoria e suporte.
          </li>
        </ul>

        <h2>3. Para que usamos e com que base legal</h2>
        <ul>
          <li>
            <strong>Executar o contrato</strong> (art. 7º, V): gerar, agendar e publicar seu
            conteúdo; manter sua conta e sua assinatura.
          </li>
          <li>
            <strong>Consentimento</strong> (art. 7º, I): conexão da sua conta do LinkedIn, que
            você concede pelo próprio LinkedIn e pode revogar a qualquer momento.
          </li>
          <li>
            <strong>Legítimo interesse</strong> (art. 7º, IX): segurança, prevenção a fraude
            no programa de indicação e melhoria do serviço.
          </li>
          <li>
            <strong>Obrigação legal</strong> (art. 7º, II): guarda de registros fiscais e de
            aplicação exigidos por lei.
          </li>
        </ul>
        <p>
          <strong>Não vendemos seus dados</strong> e não os usamos para treinar modelos de
          inteligência artificial.
        </p>

        <h2>4. Com quem compartilhamos</h2>
        <p>Apenas com operadores necessários para o serviço funcionar:</p>
        <ul>
          <li><strong>Anthropic</strong> (EUA) — geração dos textos a partir das suas pautas.</li>
          <li><strong>OpenAI</strong> (EUA) — geração de imagens, quando você solicita.</li>
          <li><strong>LinkedIn / Microsoft</strong> (EUA) — publicação dos posts que você aprova.</li>
          <li><strong>Stripe</strong> (EUA) — processamento de pagamentos.</li>
          <li><strong>Railway e Vercel</strong> (EUA) — hospedagem da aplicação e do banco de dados.</li>
        </ul>

        <h2>5. Transferência internacional</h2>
        <p>
          Como os provedores acima estão nos Estados Unidos, seus dados são transferidos para
          fora do Brasil (art. 33 da LGPD). Essas transferências ocorrem com base em cláusulas
          contratuais e garantias de proteção oferecidas por esses fornecedores, e limitam-se
          ao necessário para prestar o serviço que você contratou.
        </p>

        <h2>6. Por quanto tempo guardamos</h2>
        <p>
          Enquanto sua conta existir. Ao excluir a conta, apagamos <strong>definitivamente</strong>{" "}
          seus dados de cadastro, conteúdo, tokens e perfil, revogamos o acesso ao seu LinkedIn e
          cancelamos sua assinatura. Registros fiscais de pagamentos podem ser mantidos pela
          Stripe e por nós pelo prazo exigido em lei.
        </p>
        <p>
          Posts já publicados <strong>permanecem no seu LinkedIn</strong> — eles pertencem à sua
          conta lá, e apenas você pode removê-los pela própria plataforma.
        </p>

        <h2>7. Seus direitos (art. 18)</h2>
        <p>Você pode, a qualquer momento, direto no painel (aba <strong>Conta</strong>):</p>
        <ul>
          <li><strong>Exportar</strong> todos os seus dados em formato aberto (portabilidade);</li>
          <li><strong>Excluir</strong> sua conta e todos os dados, definitivamente;</li>
          <li><strong>Corrigir</strong> seus dados de cadastro e perfil;</li>
          <li><strong>Desconectar</strong> sua conta do LinkedIn, revogando o acesso.</li>
        </ul>
        <p>
          Para confirmação de tratamento, informações sobre compartilhamento ou qualquer outro
          direito, escreva para{" "}
          <a href="mailto:privacidade@posthink.com.br">privacidade@posthink.com.br</a>. Respondemos
          em até 15 dias.
        </p>

        <h2>8. Segurança</h2>
        <ul>
          <li>Tokens do LinkedIn criptografados em repouso (Fernet/AES).</li>
          <li>Senhas protegidas com bcrypt — irreversível, nem nós conseguimos lê-las.</li>
          <li>Tráfego sempre por HTTPS.</li>
          <li>Isolamento por usuário: seus dados nunca são acessíveis a outra conta.</li>
          <li>Nenhum dado de cartão trafega ou é armazenado em nossos servidores.</li>
        </ul>

        <h2>9. Publicação no LinkedIn</h2>
        <p>
          O Posthink publica <strong>exclusivamente pela API oficial do LinkedIn</strong>, com sua
          autorização por OAuth, e <strong>somente</strong> os posts que você aprovar
          individualmente com data e hora. Não fazemos raspagem de dados, não automatizamos
          curtidas, comentários ou conexões, e não acessamos seu feed ou suas mensagens.
        </p>

        <h2>10. Menores de idade</h2>
        <p>
          O serviço não se destina a menores de 18 anos, em linha com os termos do próprio
          LinkedIn.
        </p>

        <h2>11. Alterações</h2>
        <p>
          Podemos atualizar esta política. Mudanças relevantes serão comunicadas por e-mail ou
          no painel antes de entrarem em vigor.
        </p>

        <a className="legal-back" href="/">← Voltar ao Posthink</a>
      </div>
    </div>
  );
}
