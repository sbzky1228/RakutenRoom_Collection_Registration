# RakutenRoom Collection Registration

このリポジトリは、Rakuten ROOM にアイテムを自動で登録するための Python プログラムです。
初心者の方でも使いやすいように、手順を整理しました。

---

## 1. 何をするプログラムなのか

このプログラムは、Google スプレッドシートに書かれた情報を読み取り、
Rakuten ROOM のコレクションにアイテムを登録します。

使い方のイメージは次のとおりです。

1. Google スプレッドシートにアイテム情報を用意する
2. Python を使ってその情報を読み込む
3. Rakuten ROOM にログインして、自動でコレクション登録する
4. 登録結果をシートに書き戻す

---

## 2. 必要なもの

### ソフトウェア

- Python 3.10 以上
- Windows

### アカウント

- Rakuten ROOM のアカウント
- Google スプレッドシートの操作ができる Google アカウント
- Google サービスアカウント（Sheets API を使うための設定）

---

## 3. 準備手順

### 3-1. プロジェクトの場所に移動

PowerShell で次の場所に移動します。

```powershell
cd "c:\Users\yuki2\OneDrive\ドキュメント\プログラミング関係\プログラム(各言語)\Python_program\make_program\RakutenRoom_Collection_Registration"
```

### 3-2. Python の仮想環境を作る

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

これで、他のプロジェクトに影響を与えずに必要なパッケージを入れられます。

### 3-3. 必要なパッケージを入れる

```powershell
pip install -r requirements.txt
```

### 3-4. Playwright をインストールする

```powershell
python -m playwright install
```

---

## 4. 設定ファイル `.env` の作り方

プロジェクトの中に `.env` という名前のファイルを作り、次の内容を書きます。

```dotenv
RAKUTEN_USER_ID=your_rakuten_user_id
RAKUTEN_PASSWORD=your_rakuten_password
SPREADSHEET_ID=your_spreadsheet_id
SHEET_NAME=Sheet1
SERVICE_ACCOUNT_PATH=path\to\service_account.json
PLAYWRIGHT_BROWSERS_PATH=
CHROMIUM_EXECUTABLE_PATH=
```

### それぞれの意味

- `RAKUTEN_USER_ID`: 楽天 ROOM のログイン ID
- `RAKUTEN_PASSWORD`: 楽天 ROOM のパスワード
- `SPREADSHEET_ID`: Google スプレッドシートの ID（URL の中にあります）
- `SHEET_NAME`: 読み込むシート名（普通は `Sheet1`）
- `SERVICE_ACCOUNT_PATH`: Google のサービスアカウント JSON ファイルの場所
- `PLAYWRIGHT_BROWSERS_PATH`, `CHROMIUM_EXECUTABLE_PATH`: 普通は空のままで大丈夫です

### Google スプレッドシート ID の見つけ方

スプレッドシートの URL のこの部分が `SPREADSHEET_ID` です。

```
https://docs.google.com/spreadsheets/d/ここがID/edit
```

---

## 5. シートの列（カラム）について

このプログラムは次のような列を使います。

| 列名 | 役割 |
|---|---|
| ItemURL | 登録するアイテムの URL |
| ShopCode | 店舗コード（使われますが、処理自体には影響しません） |
| ItemID | 商品 ID（使われますが、処理自体には影響しません） |
| ItemCode | 商品コード |
| ItemName | 商品名 |
| CollectionName | 登録したいコレクション名 |
| CollectionGenre | コレクションのジャンル |
| PostStatus | 楽天市場へ投稿済みかどうか（例: `済`） |
| PostedDate | 投稿日 |
| CollectionStatus | コレクション登録の状態（`未` / `済` / `不可`） |
| CollectedDate | 登録した日付 |

### どの行を登録するか

次の条件を満たす行が対象になります。

- `PostStatus` が `済`
- `CollectionStatus` が `未`

この条件に当てはまる行だけを Rakuten ROOM に登録します。

---

## 6. 使い方

準備が終わったら、次のコマンドを実行します。

```powershell
python main.py
```

実行中にブラウザが開いて Rakuten ROOM に操作するように見えるはずです。

完了すると、`CollectionStatus` と `CollectedDate` がスプレッドシートに書き込まれます。

---

## 7. うまく動かないときの確認ポイント

### 1. `.env` の中身

- `RAKUTEN_USER_ID` と `RAKUTEN_PASSWORD` が正しいか
- `SPREADSHEET_ID` が正しいか
- `SERVICE_ACCOUNT_PATH` にサービスアカウント JSON があるか

### 2. Google スプレッドシートの見える化

サービスアカウントにシートの閲覧権限が必要です。
Google スプレッドシート側でサービスアカウントのメールアドレスを共有してください。

### 3. `config.py` のセレクタ

Rakuten ROOM の画面が変わると、`config.py` の文字列が古くなり、正しく動かなくなることがあります。
そのときは `config.py` を見直します。

---

## 8. ファイルの説明

- `main.py`: 全体の流れを動かすファイル
- `google_sheets_manager.py`: シートからデータを読み書きする部分
- `rakuten_room.py`: Rakuten ROOM にログインして登録する部分
- `config.py`: 設定や画面の部品（セレクタ）をまとめたファイル
- `requirements.txt`: 必要な Python パッケージ一覧

---

## 9. さらに初心者向けの補足

- まずは `.env` とシートだけを正しく用意することが大切です。
- うまくいかない場合は、`python main.py` を実行したときのエラーメッセージを確認してください。
- 画面が変わった場合は `config.py` を調整する必要がありますが、最初はそのまま試してみてください。
