# MachineLearning_APS

Projeto acadêmico desenvolvido com o objetivo de estudar a integração entre Hardware e Software através da construção de um ambiente de simulação para robôs de combate do tipo Sumô. O projeto explora conceitos de Inteligência Artificial, Machine Learning, robótica embarcada e tomada de decisão autônoma, permitindo a realização de milhares de combates simulados para análise e otimização de estratégias.

A motivação principal foi compreender como decisões implementadas em software podem impactar diretamente o comportamento físico de um robô, aproximando a camada computacional da execução em hardware real. Através de simulações, torna-se possível validar estratégias, reduzir custos de prototipagem e acelerar o processo de desenvolvimento antes da implementação em uma plataforma embarcada.
      
O sistema foi estruturado para permitir a criação, execução e análise de batalhas entre robôs autônomos. Durante os testes, diferentes parâmetros podem ser avaliados, como agressividade da estratégia, utilização de sensores, massa do robô, posicionamento em arena e comportamento próximo às bordas. Os resultados são registrados e utilizados para comparação de desempenho entre diferentes abordagens.

Além do ambiente de simulação desenvolvido em Python, o projeto conta com uma camada voltada para Arduino, permitindo aproximar o comportamento estudado em software da aplicação em hardware real. Essa integração foi fundamental para entender os desafios existentes entre processamento lógico, sensores, atuadores e tomada de decisão em tempo real.

Entre os principais conceitos explorados durante o desenvolvimento estão:

- Programação em Python
- Estruturas de dados
- Programação orientada a objetos
- Simulação computacional
- Inteligência Artificial
- Machine Learning aplicado à tomada de decisão
- Estatística e análise de desempenho
- Sistemas embarcados com Arduino
- Integração Hardware x Software

O fluxo geral do projeto segue as seguintes etapas:

1. Definição das estratégias de combate.
2. Execução de centenas ou milhares de simulações.
3. Coleta automática dos resultados.
4. Análise estatística do desempenho obtido.
5. Comparação entre estratégias e parâmetros.
6. Identificação das melhores configurações para implementação física.

A arquitetura do projeto foi organizada para separar a simulação, análise dos dados e integração embarcada, permitindo evolução contínua e maior facilidade de manutenção.
