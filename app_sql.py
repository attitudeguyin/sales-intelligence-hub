import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
from groq import Groq

st.set_page_config(page_title='Sales Intelligence Hub', page_icon='📊', layout='wide')
st.title('📊 Sales Intelligence Hub')
st.caption('Ask anything about your sales data — powered by Groq + Llama 3.3')

client = Groq(api_key=st.secrets['GROQ_API_KEY'])

DB_SCHEMA = '''
You have access to a Sales CRM SQLite database with these tables:
1. customers (customer_id, name, email, city, state, segment, created_date)
2. products (product_id, product_name, category, unit_price, cost_price)
3. sales (sale_id, customer_id, product_id, quantity, sale_date, revenue, discount, region, salesperson)
4. support_tickets (ticket_id, customer_id, issue_type, status, priority, created_date, resolved_date)
'''

def generate_sql(question):
    prompt = DB_SCHEMA + '\nConvert this question to SQLite SQL. Return ONLY the SQL, no explanation, no backticks.\n\nQuestion: ' + question + '\nSQL:'
    response = client.chat.completions.create(
        model='llama-3.3-70b-versatile',
        messages=[{'role': 'user', 'content': prompt}],
        max_tokens=512,
        temperature=0.1
    )
    sql = response.choices[0].message.content.strip()
    sql = sql.replace('```sql', '').replace('```', '').strip()
    if ';' in sql:
        sql = sql.split(';')[0].strip() + ';'
    return sql

def execute_sql(sql):
    conn = sqlite3.connect('sales_crm.db')
    try:
        df = pd.read_sql_query(sql, conn)
        return df, None
    except Exception as e:
        return None, str(e)
    finally:
        conn.close()

def generate_insight(question, df):
    data_str = df.to_string(index=False) if len(df) <= 20 else df.head(20).to_string(index=False)
    prompt = 'You are a senior business analyst. User asked: ' + question + '\nData:\n' + data_str + '\nWrite 2-3 sentence business insight with recommendation. Use Indian Rupee crore/lakh format.'
    response = client.chat.completions.create(
        model='llama-3.3-70b-versatile',
        messages=[{'role': 'user', 'content': prompt}],
        max_tokens=256
    )
    return response.choices[0].message.content.strip()

def auto_chart(df, question, chart_key):
    if df is None or df.empty or len(df.columns) < 2:
        return
    cols = df.columns.tolist()
    num_cols = df.select_dtypes(include='number').columns.tolist()
    str_cols = df.select_dtypes(include='object').columns.tolist()
    q_lower = question.lower()
    try:
        if any(w in q_lower for w in ['month', 'trend', 'over time', 'daily', 'weekly']):
            if len(num_cols) >= 1:
                fig = px.line(df, x=cols[0], y=num_cols[0], title='Trend Over Time')
                st.plotly_chart(fig, use_container_width=True, key=chart_key)
                return
        if len(str_cols) >= 1 and len(num_cols) >= 1 and len(df) <= 8:
            fig = px.pie(df, names=str_cols[0], values=num_cols[0], title='Distribution of ' + num_cols[0])
            st.plotly_chart(fig, use_container_width=True, key=chart_key)
            return
        if len(str_cols) >= 1 and len(num_cols) >= 1:
            fig = px.bar(df, x=str_cols[0], y=num_cols[0], title=num_cols[0] + ' by ' + str_cols[0], color=num_cols[0], color_continuous_scale='Blues')
            st.plotly_chart(fig, use_container_width=True, key=chart_key)
    except Exception:
        pass

with st.sidebar:
    st.header('💡 Quick Questions')
    quick_questions = [
        'Top 5 customers by revenue',
        'Revenue by product category',
        'Show monthly revenue trend for 2023',
        'Best performing salesperson',
        'Revenue by region',
        'Open support tickets by priority',
        'Top 5 products by quantity sold',
        'Which city has highest sales?',
        'Which product has the highest profit margin?',
        'Customer segment revenue breakdown',
    ]
    for q in quick_questions:
        if st.button(q, use_container_width=True):
            st.session_state.quick_q = q
    st.divider()
    st.success('⚡ Powered by Groq + Llama 3.3 70B')
    st.info('15 customers | 10 products | 1,074 sales | 200 tickets')

if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'quick_q' not in st.session_state:
    st.session_state.quick_q = None

for i, msg in enumerate(st.session_state.messages):
    with st.chat_message(msg['role']):
        st.markdown(msg['content'])
        if msg['role'] == 'assistant':
            if 'sql' in msg:
                with st.expander('🔍 SQL Generated'):
                    st.code(msg['sql'], language='sql')
            if 'dataframe' in msg and msg['dataframe'] is not None:
                auto_chart(msg['dataframe'], msg.get('question', ''), 'history_chart_' + str(i))
                with st.expander('📋 View raw data'):
                    st.dataframe(msg['dataframe'], use_container_width=True)

question = st.chat_input('Ask anything about your sales data...')
if st.session_state.quick_q:
    question = st.session_state.quick_q
    st.session_state.quick_q = None

if question:
    st.session_state.messages.append({'role': 'user', 'content': question})
    with st.chat_message('user'):
        st.markdown(question)
    with st.chat_message('assistant'):
        with st.spinner('🧠 Converting to SQL...'):
            sql = generate_sql(question)
        with st.expander('🔍 SQL Generated'):
            st.code(sql, language='sql')
        with st.spinner('⚡ Querying database...'):
            df, error = execute_sql(sql)
        if error:
            st.error('SQL Error: ' + error)
            st.session_state.messages.append({'role': 'assistant', 'content': 'SQL Error: ' + error})
        else:
            with st.spinner('💡 Generating insight...'):
                insight = generate_insight(question, df)
            st.markdown('### 💡 Insight\n' + insight)
            auto_chart(df, question, 'new_chart_' + str(len(st.session_state.messages)))
            with st.expander('📋 View raw data'):
                st.dataframe(df, use_container_width=True)
            st.session_state.messages.append({
                'role': 'assistant',
                'content': '### 💡 Insight\n' + insight,
                'sql': sql,
                'dataframe': df,
                'question': question
            })


