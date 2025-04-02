import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import requests
import json
import re
from datetime import datetime, timedelta
import time
from textblob import TextBlob
from googleapiclient.discovery import build
from newsapi import NewsApiClient
from pytube import YouTube
from youtube_transcript_api import YouTubeTranscriptApi
import plotly.express as px
import plotly.graph_objects as go

# Konfigurasi halaman
st.set_page_config(page_title="Sistem Analisis Sentimen Berita", page_icon="📰", layout="wide")

# Fungsi untuk mendapatkan berita dari NewsAPI
def get_news(query, from_date, to_date, language='id', sort_by='publishedAt'):
    try:
        # Inisialisasi NewsAPI
        newsapi = NewsApiClient(api_key=news_api_key)
        
        # Mendapatkan berita
        all_articles = newsapi.get_everything(q=query,
                                            from_param=from_date,
                                            to=to_date,
                                            language=language,
                                            sort_by=sort_by)
        
        # Menyusun data
        articles = []
        for article in all_articles['articles']:
            articles.append({
                'title': article['title'],
                'source': article['source']['name'],
                'author': article['author'],
                'published_at': article['publishedAt'],
                'url': article['url'],
                'content': article['content'],
                'description': article['description']
            })
        
        return pd.DataFrame(articles)
    except Exception as e:
        st.error(f"Error dalam mengambil berita: {e}")
        return pd.DataFrame()

# Fungsi untuk mencari video YouTube
def search_youtube_videos(query, max_results=10):
    try:
        # Membangun layanan YouTube
        youtube = build('youtube', 'v3', developerKey=youtube_api_key)
        
        # Melakukan pencarian
        search_response = youtube.search().list(
            q=query,
            part='id,snippet',
            maxResults=max_results,
            type='video'
        ).execute()
        
        # Menyusun data
        videos = []
        for item in search_response['items']:
            video_id = item['id']['videoId']
            videos.append({
                'title': item['snippet']['title'],
                'channel': item['snippet']['channelTitle'],
                'published_at': item['snippet']['publishedAt'],
                'video_id': video_id,
                'url': f'https://www.youtube.com/watch?v={video_id}'
            })
        
        return pd.DataFrame(videos)
    except Exception as e:
        st.error(f"Error dalam pencarian video YouTube: {e}")
        return pd.DataFrame()

# Fungsi untuk mendapatkan transkrip video YouTube
def get_youtube_transcript(video_id, languages=['id', 'en']):
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=languages)
        transcript_text = ' '.join([t['text'] for t in transcript_list])
        return transcript_text
    except Exception as e:
        st.warning(f"Tidak dapat mengambil transkrip untuk video ini: {e}")
        return ""

# Fungsi untuk analisis sentimen menggunakan TextBlob
def analyze_sentiment(text):
    if not text or pd.isna(text):
        return {'polarity': 0, 'subjectivity': 0, 'sentiment': 'netral'}
    
    analysis = TextBlob(text)
    polarity = analysis.sentiment.polarity
    subjectivity = analysis.sentiment.subjectivity
    
    # Menentukan kategori sentimen
    if polarity > 0.2:
        sentiment = 'positif'
    elif polarity < -0.2:
        sentiment = 'negatif'
    else:
        sentiment = 'netral'
    
    return {
        'polarity': polarity,
        'subjectivity': subjectivity,
        'sentiment': sentiment
    }

# Fungsi untuk visualisasi sentimen
def visualize_sentiment(df):
    if df.empty:
        st.warning("Tidak ada data untuk divisualisasikan")
        return
    
    # Menghitung jumlah sentimen per kategori
    sentiment_counts = df['sentiment'].value_counts().reset_index()
    sentiment_counts.columns = ['Sentimen', 'Jumlah']
    
    # Membuat diagram lingkaran
    fig1 = px.pie(sentiment_counts, values='Jumlah', names='Sentimen', 
                 title='Distribusi Sentimen',
                 color='Sentimen',
                 color_discrete_map={'positif':'green', 'netral':'blue', 'negatif':'red'})
    
    st.plotly_chart(fig1)
    
    # Membuat diagram batang untuk sumber berita teratas
    if 'source' in df.columns:
        top_sources = df.groupby(['source', 'sentiment']).size().reset_index(name='count')
        fig2 = px.bar(top_sources, x='source', y='count', color='sentiment',
                     title='Analisis Sentimen per Sumber',
                     color_discrete_map={'positif':'green', 'netral':'blue', 'negatif':'red'})
        st.plotly_chart(fig2)
    
    # Tren sentimen berdasarkan waktu
    if 'published_at' in df.columns:
        df['date'] = pd.to_datetime(df['published_at']).dt.date
        date_sentiment = df.groupby(['date', 'sentiment']).size().reset_index(name='count')
        
        fig3 = px.line(date_sentiment, x='date', y='count', color='sentiment',
                      title='Tren Sentimen Berdasarkan Waktu',
                      color_discrete_map={'positif':'green', 'netral':'blue', 'negatif':'red'})
        st.plotly_chart(fig3)

# Fungsi untuk menampilkan hasil analisis
def display_results(df, source_type):
    if df.empty:
        st.warning(f"Tidak ada {source_type} yang ditemukan")
        return
    
    # Menampilkan informasi dasar
    st.subheader(f"Hasil Analisis {source_type}")
    st.write(f"Jumlah {source_type} yang dianalisis: {len(df)}")
    
    # Distribusi sentimen
    sentiment_distribution = df['sentiment'].value_counts()
    st.write("Distribusi Sentimen:")
    st.write(sentiment_distribution)
    
    # Menampilkan hasil dalam tabel
    st.subheader(f"Tabel Data {source_type}")
    st.dataframe(df)
    
    # Visualisasi
    st.subheader(f"Visualisasi Sentimen {source_type}")
    visualize_sentiment(df)
    
    # Detail item dengan sentimen tertinggi/terendah
    st.subheader(f"{source_type} dengan Sentimen Tertinggi")
    most_positive = df.loc[df['polarity'].idxmax()]
    st.write(f"Judul: {most_positive.get('title', 'Tidak tersedia')}")
    st.write(f"Polaritas: {most_positive['polarity']:.4f}")
    st.write(f"URL: {most_positive.get('url', 'Tidak tersedia')}")
    
    st.subheader(f"{source_type} dengan Sentimen Terendah")
    most_negative = df.loc[df['polarity'].idxmin()]
    st.write(f"Judul: {most_negative.get('title', 'Tidak tersedia')}")
    st.write(f"Polaritas: {most_negative['polarity']:.4f}")
    st.write(f"URL: {most_negative.get('url', 'Tidak tersedia')}")

# UI utama
st.title("📰 Sistem Analisis Sentimen Berita")
st.markdown("""
Sistem ini mencari dan menganalisis sentimen berita dari internet, baik dalam bentuk teks maupun video.
""")

# Sidebar untuk pengaturan API
with st.sidebar:
    st.header("Konfigurasi API")
    news_api_key = st.text_input("NewsAPI Key", type="password")
    youtube_api_key = st.text_input("YouTube API Key", type="password")
    
    st.header("Pengaturan Pencarian")
    query = st.text_input("Kata Kunci Pencarian")
    
    col1, col2 = st.columns(2)
    with col1:
        days_ago = st.number_input("Cari berita dari berapa hari lalu", min_value=1, max_value=30, value=7)
    with col2:
        language = st.selectbox("Bahasa", options=['id', 'en'], index=0)
    
    max_results = st.slider("Jumlah maksimum hasil", min_value=5, max_value=50, value=10)
    
    search_type = st.multiselect("Jenis Pencarian", ['Berita Teks', 'Video YouTube'], default=['Berita Teks'])
    
    analyze_button = st.button("Analisis Sentimen")

# Area utama untuk hasil
if analyze_button and query:
    if not news_api_key and 'Berita Teks' in search_type:
        st.error("Mohon masukkan NewsAPI Key untuk mencari berita teks")
    
    if not youtube_api_key and 'Video YouTube' in search_type:
        st.error("Mohon masukkan YouTube API Key untuk mencari video")
    
    if (news_api_key and 'Berita Teks' in search_type) or (youtube_api_key and 'Video YouTube' in search_type):
        # Menampilkan spinner selama pencarian dan analisis
        with st.spinner("Sedang mencari dan menganalisis..."):
            # Pengaturan tanggal
            to_date = datetime.now().strftime('%Y-%m-%d')
            from_date = (datetime.now() - timedelta(days=days_ago)).strftime('%Y-%m-%d')
            
            # Membuat tab untuk setiap jenis pencarian
            tabs = st.tabs([type_name for type_name in search_type] + ["Rangkuman"])
            
            all_results = {}
            
            # Proses untuk berita teks
            if 'Berita Teks' in search_type and news_api_key:
                with tabs[search_type.index('Berita Teks')]:
                    st.header("Analisis Berita Teks")
                    
                    # Mencari berita
                    news_df = get_news(query, from_date, to_date, language)
                    
                    if not news_df.empty:
                        # Analisis sentimen
                        sentiment_results = []
                        for _, row in news_df.iterrows():
                            # Menggunakan deskripsi dan konten untuk analisis
                            text_to_analyze = f"{row['title']} {row['description']} {row['content']}"
                            sentiment_data = analyze_sentiment(text_to_analyze)
                            sentiment_results.append(sentiment_data)
                        
                        # Menambahkan hasil sentimen ke dataframe
                        news_df['polarity'] = [r['polarity'] for r in sentiment_results]
                        news_df['subjectivity'] = [r['subjectivity'] for r in sentiment_results]
                        news_df['sentiment'] = [r['sentiment'] for r in sentiment_results]
                        
                        # Menampilkan hasil
                        display_results(news_df, "Berita Teks")
                        all_results['Berita Teks'] = news_df
                    else:
                        st.warning("Tidak ada berita yang ditemukan. Coba kata kunci lain atau perpanjang rentang waktu.")
            
            # Proses untuk video YouTube
            if 'Video YouTube' in search_type and youtube_api_key:
                with tabs[search_type.index('Video YouTube')]:
                    st.header("Analisis Video YouTube")
                    
                    # Mencari video
                    videos_df = search_youtube_videos(query, max_results)
                    
                    if not videos_df.empty:
                        # Progress bar untuk analisis transkrip
                        progress_bar = st.progress(0)
                        progress_text = st.empty()
                        
                        # Mendapatkan dan menganalisis transkrip
                        transcripts = []
                        sentiment_results = []
                        
                        for i, (_, row) in enumerate(videos_df.iterrows()):
                            progress_text.text(f"Menganalisis video {i+1} dari {len(videos_df)}")
                            
                            # Mendapatkan transkrip
                            transcript = get_youtube_transcript(row['video_id'], languages=[language, 'en'])
                            transcripts.append(transcript)
                            
                            # Analisis sentimen
                            if transcript:
                                sentiment_data = analyze_sentiment(transcript)
                            else:
                                sentiment_data = {'polarity': 0, 'subjectivity': 0, 'sentiment': 'tidak ada transkrip'}
                            
                            sentiment_results.append(sentiment_data)
                            progress_bar.progress((i + 1) / len(videos_df))
                        
                        # Menambahkan transkrip dan hasil sentimen ke dataframe
                        videos_df['transcript'] = transcripts
                        videos_df['polarity'] = [r['polarity'] for r in sentiment_results]
                        videos_df['subjectivity'] = [r['subjectivity'] for r in sentiment_results]
                        videos_df['sentiment'] = [r['sentiment'] for r in sentiment_results]
                        
                        # Membersihkan progress bar
                        progress_bar.empty()
                        progress_text.empty()
                        
                        # Menampilkan hasil
                        display_results(videos_df, "Video YouTube")
                        all_results['Video YouTube'] = videos_df
                    else:
                        st.warning("Tidak ada video yang ditemukan. Coba kata kunci lain.")
            
            # Tab rangkuman
            with tabs[-1]:
                st.header("Rangkuman Analisis Sentimen")
                
                if all_results:
                    # Menggabungkan hasil
                    summary_data = []
                    for source_type, df in all_results.items():
                        if not df.empty:
                            source_summary = {
                                'Jenis': source_type,
                                'Jumlah': len(df),
                                'Positif': sum(df['sentiment'] == 'positif'),
                                'Netral': sum(df['sentiment'] == 'netral'),
                                'Negatif': sum(df['sentiment'] == 'negatif'),
                                'Rata-rata Polaritas': df['polarity'].mean(),
                                'Rata-rata Subjektivitas': df['subjectivity'].mean()
                            }
                            summary_data.append(source_summary)
                    
                    if summary_data:
                        summary_df = pd.DataFrame(summary_data)
                        st.write("Rangkuman hasil analisis:")
                        st.dataframe(summary_df)
                        
                        # Visualisasi rangkuman
                        fig = go.Figure()
                        
                        for source_type in summary_df['Jenis']:
                            row = summary_df[summary_df['Jenis'] == source_type].iloc[0]
                            fig.add_trace(go.Bar(
                                name=source_type,
                                x=['Positif', 'Netral', 'Negatif'],
                                y=[row['Positif'], row['Netral'], row['Negatif']],
                                marker_color=['green', 'blue', 'red']
                            ))
                        
                        fig.update_layout(
                            title='Perbandingan Distribusi Sentimen',
                            xaxis_title='Kategori Sentimen',
                            yaxis_title='Jumlah',
                            barmode='group'
                        )
                        
                        st.plotly_chart(fig)
                        
                        # Analisis akhir
                        st.subheader("Kesimpulan")
                        
                        # Menghitung total sentimen
                        total_positive = sum(row['Positif'] for row in summary_data)
                        total_neutral = sum(row['Netral'] for row in summary_data)
                        total_negative = sum(row['Negatif'] for row in summary_data)
                        total_items = sum(row['Jumlah'] for row in summary_data)
                        
                        st.write(f"Dari total {total_items} item yang dianalisis:")
                        st.write(f"- {total_positive} ({total_positive/total_items*100:.1f}%) memiliki sentimen positif")
                        st.write(f"- {total_neutral} ({total_neutral/total_items*100:.1f}%) memiliki sentimen netral")
                        st.write(f"- {total_negative} ({total_negative/total_items*100:.1f}%) memiliki sentimen negatif")
                        
                        # Memberikan kesimpulan akhir
                        if total_positive > (total_neutral + total_negative):
                            st.write(f"**Kesimpulan:** Topik '{query}' cenderung memiliki sentimen **POSITIF** pada pemberitaan dan media.")
                        elif total_negative > (total_neutral + total_positive):
                            st.write(f"**Kesimpulan:** Topik '{query}' cenderung memiliki sentimen **NEGATIF** pada pemberitaan dan media.")
                        else:
                            st.write(f"**Kesimpulan:** Topik '{query}' cenderung memiliki sentimen **NETRAL** atau CAMPURAN pada pemberitaan dan media.")
                else:
                    st.warning("Tidak ada data yang dianalisis.")
                    
        # Tambahkan opsi untuk mengunduh hasil
        if all_results:
            st.subheader("Unduh Hasil Analisis")
            
            for source_type, df in all_results.items():
                if not df.empty:
                    csv = df.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label=f"Unduh hasil {source_type} (CSV)",
                        data=csv,
                        file_name=f"analisis_sentimen_{source_type.lower().replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.csv",
                        mime="text/csv"
                    )

else:
    st.info("Masukkan kata kunci pencarian dan klik 'Analisis Sentimen' untuk memulai.")
    
    # Contoh penggunaan
    with st.expander("Panduan Penggunaan"):
        st.markdown("""
        ### Cara Menggunakan Sistem Ini
        
        1. **Konfigurasi API**
           - Dapatkan API key dari [NewsAPI](https://newsapi.org) dan [Google Cloud Console (untuk YouTube API)](https://console.cloud.google.com)
           - Masukkan API key pada form di sidebar
        
        2. **Pengaturan Pencarian**
           - Masukkan kata kunci pencarian
           - Pilih rentang waktu untuk berita
           - Pilih bahasa (Indonesia atau Inggris)
           - Pilih jenis pencarian (Berita Teks, Video YouTube, atau keduanya)
        
        3. **Analisis Hasil**
           - Lihat distribusi sentimen (positif, netral, negatif)
           - Periksa tren sentimen berdasarkan waktu
           - Identifikasi berita/video dengan sentimen tertinggi dan terendah
        
        ### Contoh Kata Kunci:
        - "Pemilu Indonesia"
        - "Ekonomi digital"
        - "Pendidikan online"
        - "Startup teknologi"
        - "Perubahan iklim"
        """)

# Footer
st.markdown("---")
st.markdown("© 2025 Sistem Analisis Sentimen Berita | Dibuat dengan Streamlit, NewsAPI, dan YouTube API")