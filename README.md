# 楽天ROOMコレクション登録プログラム - Playwright版

## 概要

楽天ROOMに投稿済みの商品を、Googleスプレッドシートに書いたコレクション名の「コレクション」へ自動で登録するツールです。

- スプレッドシートで **PostStatus が「済」**（ROOMに投稿済み）かつ **CollectionStatus が「未」** の商品が対象です。
- **CollectionName** に書いたコレクションが
  - すでにある場合 → そのコレクションに商品を追加します（もともと入っている商品はそのままです）
  - まだ無い場合 → ジャンル「すべてのジャンル」でコレクションを新しく作り、商品を登録します
- 登録が終わったら、CollectionStatus を「済」にし、CollectedDate に登録日を書き込みます。
- 1回の実行で、対象の商品をすべて処理します（タスクスケジューラ等で定期実行する想定です）。

## プログラム構成

| ファイル | 役割 |
|---|---|
| `main.py` | メイン処理（各モジュールを順番に呼び出し、処理の流れを制御する） |
| `config.py` | `.env` の読み込みと設定値・定数の管理、保存先（`user_data`・`logs`）の決定 |
| `logger.py` | ログ出力（コンソールとログファイル） |
| `browser_manager.py` | Playwright（Chromium）の起動・終了、ログインセッションの保存（`user_data`）、パスキー要求のキャンセル |
| `rakuten_login.py` | 楽天へのログイン判定・ログイン処理、再認証 |
| `room_collection.py` | 楽天ROOMのコレクション一覧の確認、コレクションの作成・商品の登録、保存されたかの確認 |
| `google_sheets_utils.py` | Google Sheets APIへの接続（サービスアカウント認証）とデータ取得 |
| `google_sheets_manager.py` | 登録対象の抽出（コレクション名ごとにまとめる）、CollectionStatus の更新 |
| `tests\` | 自動テスト（ブラウザ・スプレッドシートを使わずに動作を確認する） |
| `.github\workflows\tests.yml` | GitHub Actions の設定（GitHubにpushしたときに自動テストを実行する） |
| `requirements-dev.txt` | テスト用のパッケージ（pytest・pyflakes・vulture） |
| `.env.example` | `.env`（設定ファイル）のひな形 |

### 処理フロー

```
1. スプレッドシートから、PostStatus「済」かつ CollectionStatus「未」の商品を取得
   └─ 対象が無い → ブラウザを起動せずに終了
2. 商品を CollectionName ごとにまとめる
3. ブラウザ起動（user_data に保存されたログインセッションを読み込む）
4. 楽天へのログイン
   ├─ ログイン済み（セッションが有効）→ そのまま次へ
   └─ 未ログイン → ID・パスワードでログイン（パスキーはキャンセルしてパスワードを使用）
5. 楽天ROOMの「my ROOM」⇒「コレクション」を開き、作成済みのコレクションを確認
6. コレクションごとに商品を登録
   ├─ 作成済み → 編集画面で商品にチェックを入れて「完了」
   └─ 未作成   → 「新規コレクションを作成する」で作成
                 （ジャンルが「すべてのジャンル」であることを確認し、コレクション名を入力して「完了」）
   └─ 保存後に編集画面を開き直し、商品が本当に入ったかを確認
7. コレクションごとにスプレッドシートを更新（下の表を参照）
8. ブラウザ終了
```

### 商品の見分け方

ROOMのコレクション編集画面に表示される「ROOMに投稿した商品」と、スプレッドシートの **ItemURL** を照合します。
ROOMに表示される商品名は、ショップがクーポン・セールの文言を足すなどして変わるため、商品名では照合しません。
（ItemName は、先頭の「【楽天市場】」と末尾の「：ショップ名」を除いてログの表示に使います。）

## 必要な環境

- Windows
- Python 3.10以上（開発・動作確認は Python 3.12）
- 楽天会員アカウント（パスワードでログインできること。楽天ROOMを利用していること）
- Googleアカウント（Google Cloud のサービスアカウント、Googleスプレッドシート）

## セットアップ手順

### 1. 環境構築

PowerShell（ターミナル）でプロジェクトのフォルダに移動してから、次のコマンドを順番に実行します。

```powershell
# 仮想環境の作成
python -m venv venv

# 仮想環境の有効化
.\venv\Scripts\activate

# パッケージのインストール
pip install -r requirements.txt

# Playwrightのブラウザをインストール
playwright install chromium
```

### 2. .env ファイルの作成

`.env.example` をコピーして `.env` という名前で保存し、自分の情報に書き換えます。

| 項目 | 必須 | 内容 |
|---|---|---|
| `RAKUTEN_USER_ID` | 必須 | 楽天会員のユーザーID（またはメールアドレス） |
| `RAKUTEN_PASSWORD` | 必須 | 楽天会員のパスワード |
| `SPREADSHEET_ID` | 必須 | スプレッドシートのID（URL `https://docs.google.com/spreadsheets/d/<ここ>/edit` の部分） |
| `SHEET_NAME` | 必須 | シート名（画面下のタブに表示されている名前） |
| `SERVICE_ACCOUNT_PATH` | 必須 | サービスアカウントのJSONキーのパス（`.env` と同じフォルダに置き、ファイル名だけ書くのが簡単） |
| `LOG_DIR` | 任意 | ログの保存先（未指定ならプログラムのフォルダの `logs`） |
| `PLAYWRIGHT_BROWSERS_PATH` | 任意 | Playwrightのブラウザのインストール先（通常は指定不要） |

```dotenv
RAKUTEN_USER_ID='your_user_id_or_email'
RAKUTEN_PASSWORD='your_password'
SPREADSHEET_ID='your_spreadsheet_id'
SHEET_NAME='リスト'
SERVICE_ACCOUNT_PATH='service_account.json'
```

> **Windowsのパスは「シングルクォート（'）」で囲んでください。**
> ダブルクォート（"）で囲むと、`\r` や `\n` が改行文字として読まれてパスが壊れます。
> - OK: `SERVICE_ACCOUNT_PATH='C:\Users\you\service_account.json'`
> - NG: `SERVICE_ACCOUNT_PATH="C:\Users\you\service_account.json"`

### 3. Google認証の設定

1. Google Cloud でサービスアカウントを作成し、JSONキーをダウンロードします。
2. JSONキーを `service_account.json` という名前でプロジェクトのフォルダ（`.env` と同じ場所）に置きます。
3. 対象のスプレッドシートを開き、「共有」からサービスアカウントのメールアドレス（JSONキーの `client_email`）を「編集者」として追加します。

> `.env`・JSONキーはパスワードと同じ扱いです。他人に渡したりGitにコミットしたりしないでください（`.gitignore` で除外済み）。

### 4. スプレッドシートの準備

1行目に次の見出しを付けてください。列は見出し名で探すため、列の順番は変わっても動作します（見出し名は変えないでください）。

| 見出し | このプログラムでの使い方 |
|---|---|
| ItemURL | 商品ページのURL（**ROOMの商品との照合に使う**） |
| ShopCode | 使わない |
| ItemID | 使わない |
| ItemCode | ログの表示に使う |
| ItemName | ログの表示に使う |
| CollectionName | **登録先のコレクション名**（50文字以内）。空欄の行は登録しない |
| CollectionGenre | 使わない（新規作成時のジャンルは常に「すべてのジャンル」） |
| PostStatus | 「済」の行が対象 |
| PostedDate | 使わない |
| CollectionStatus | 「未」の行が対象。処理後に下の表のとおり更新する |
| CollectedDate | 処理した日付を書き込む |

**CollectionStatus の更新内容**

| 値 | 意味 | 次回の実行 |
|---|---|---|
| 済 | コレクションに登録した（または、すでに登録されていた） | 対象外 |
| 不可 | ROOMに投稿した商品の中に見つからない、またはコレクションの上限（100件）を超えた | 対象外 |
| 未のまま | エラー、保存を確認できなかった、商品一覧を最後まで読み込めなかった など | **もう一度登録を試す** |

- CollectionName が空欄の行は登録せず「未」のまま残します。記入すれば次回の実行で登録されます。
- コレクション名の全角・半角や、前後・連続したスペースの違いは同じ名前として扱います（例:「キッチン　」と「キッチン」は同じコレクション）。
- 同じ商品の行が複数ある場合は、すべての行を同じように更新します。

## 実行方法

### 通常実行

```powershell
.\venv\Scripts\activate
python main.py
```

> **実際に楽天ROOMのコレクションを作成・更新し、スプレッドシートも更新します。**

### ログインとセッションの保存（user_data）

- 一度ログインすると、ログイン状態（Cookie）が `user_data` フォルダに保存され、次回以降はログインを省略します。
  - `python main.py` 実行時: プロジェクト直下の `user_data`
  - `.exe` 実行時: `RakutenRoomCollection.exe` と同じフォルダの `user_data`
- 初回（`user_data` が無い・中身を削除した）や、セッションが切れている場合は自動でログインします。
  - 楽天からパスキー認証を求められますが、自動でキャンセルしてパスワードでログインします（パスキーのQRコードは表示されません）。
- 楽天ROOMの操作中に再認証を求められた場合も、自動でパスワードを入力して続行します。
- アカウントロックを防ぐため、ID・パスワードの送信は1回のログイン処理につき1回だけです（失敗しても再送信しません）。
- ログイン状態をリセットしたい場合は `user_data` フォルダを削除してください。

### 自動テスト

ブラウザやスプレッドシートを使わずに、プログラムの動作（対象の抽出、結果の振り分け、スプレッドシートへの書き込み内容など）を確認できます。
コードを修正したときに実行してください。

```powershell
pip install -r requirements-dev.txt     # 初回のみ（pytest などテスト用のツールを入れる）
python -m pytest tests
```

`25 passed` のように表示され、`failed` が無ければ問題ありません。

#### GitHubでの自動テスト（GitHub Actions）

GitHubにpush（またはプルリクエストを作成）すると、GitHub上で自動的にテストが実行されます（設定ファイル: `.github/workflows/tests.yml`）。
楽天やスプレッドシートには接続しないため、`.env` やJSONキーをGitHubに置く必要はありません。

- 結果の見方: GitHubのリポジトリの「Actions」タブを開くと、実行ごとに ✅（成功）か ❌（失敗）が表示されます。❌ をクリックすると、どのテストが失敗したか確認できます。
- 手動で実行: 「Actions」タブ →「テスト」→「Run workflow」
- 失敗したときは、パソコンで `python -m pytest tests` を実行して同じエラーが出るか確認し、修正してから再度pushしてください。

## 実行ファイル（.exe）の作成

Pythonが入っていないパソコンでも動かせるように、プログラムを1つの実行ファイル（`RakutenRoomCollection.exe`）にまとめます。
タスクスケジューラで定期実行する場合も、この実行ファイルを使います。

> **コードを修正したときは、必ず実行ファイルを作り直してください。** 作り直さないと、修正は実行ファイルに反映されません。

### 1. 実行ファイルを作成する手順

**事前準備**: 「[セットアップ手順](#セットアップ手順)」の「1. 環境構築」を済ませ、`python main.py` で動くことを確認しておいてください。

**手順1. プロジェクトのフォルダでターミナルを開く**

エクスプローラーでプロジェクトのフォルダ（`main.py` があるフォルダ）を開き、フォルダ内の何もないところを右クリックして「ターミナルで開く」を選びます。
（表示されない場合は「その他のオプションを確認」→「ターミナルで開く」、または PowerShell を起動して `cd` でフォルダに移動します。）

```powershell
cd "C:\path\to\RakutenRoom_Collection_Registration"
```

**手順2. 仮想環境を有効にする**

```powershell
.\venv\Scripts\activate
```

行の先頭に `(venv)` と表示されれば有効になっています。

**手順3. PyInstaller をインストールする**（初回のみ）

実行ファイルの作成には PyInstaller というツールを使います（`requirements.txt` には含まれていないため、別途インストールします）。

```powershell
pip install pyinstaller
```

**手順4. 実行ファイルを作成する**

初回は次のコマンドを実行します。

```powershell
pyinstaller --noconfirm --clean --onefile --name RakutenRoomCollection --workpath "$env:TEMP\RakutenRoomCollection_build" main.py
```

- 1〜2分ほどかかります。最後に `Build complete!` と表示されれば成功です。
- `--workpath ...` は、作成時の作業フォルダを OneDrive の外（一時フォルダ）に置く指定です。
  OneDrive 内で作業すると、同期と重なって `PermissionError: [WinError 5] アクセスが拒否されました` で失敗することがあるためです。
- `--clean` は前回の作業内容を使わずに作り直す指定です。付けないと「変更なし」と判断されて**作り直されない**ことがあります。

2回目以降（作り直す場合）は、1回目に作られた設定ファイル（`RakutenRoomCollection.spec`）を使って次のコマンドで作成できます。

```powershell
pyinstaller --noconfirm --clean --workpath "$env:TEMP\RakutenRoomCollection_build" RakutenRoomCollection.spec
```

- 作り直すときは、実行中の `RakutenRoomCollection.exe` を終了してから実行してください（実行中は上書きできません）。

**手順5. できあがったファイルを確認する**

```
RakutenRoom_Collection_Registration\
├─ dist\
│   └─ RakutenRoomCollection.exe   … できあがった実行ファイル
└─ RakutenRoomCollection.spec       … 作成時の設定ファイル（作り直しで使う）
```

`RakutenRoomCollection.exe` の更新日時が、今作成した日時になっていることを確認してください。

**手順6. 必要なファイルを配置して試しに実行する**

1. 次の「[2. 実行時に必要な外部ファイル](#2-実行時に必要な外部ファイル)」のとおり、`dist` フォルダに `.env` と `service_account.json` を置きます。
2. `RakutenRoomCollection.exe` をダブルクリックして実行します。
   - 黒い画面（コンソール）とブラウザが開き、自動で処理が進みます。処理が終わると自動で閉じます。
   - 対象の商品が無い場合は、ブラウザを開かずにすぐ終わります。
   - **対象の商品がある場合は、実際にROOMのコレクションへ登録され、スプレッドシートも更新されます。**
3. `dist\logs` フォルダにできたログファイルを開き、`楽天ROOMコレクション登録プログラムが完了しました`（対象が無い場合は `コレクションに登録する商品がありません`）と記録されていること、`[ERROR]` が無いことを確認します。

### 2. 実行時に必要な外部ファイル

実行ファイルと同じフォルダに `.env` を配置してください。実行ファイルは、自分と同じフォルダの `.env` を探して読み込みます。

```
dist\
├─ RakutenRoomCollection.exe
├─ .env                    … .env.example をコピーして作成
├─ service_account.json    … SERVICE_ACCOUNT_PATH で指定（同じフォルダに置くのが簡単）
├─ user_data\              … 初回実行時に自動作成（ログインセッション）
└─ logs\                   … 実行時に自動作成（ログファイル）
```

### 3. Playwright のブラウザが必要

実行ファイルでも Playwright のブラウザがインストールされている必要があります。

```powershell
playwright install chromium
```

- Windows では通常、`%LOCALAPPDATA%\ms-playwright`（例: `C:\Users\<ユーザー名>\AppData\Local\ms-playwright`）にインストールされ、実行ファイルはこのフォルダを自動で使用します。
- 実行ファイルに含まれる Playwright（1.40.0）に対応したブラウザ（`chromium-1091`）が必要です。`requirements.txt` でインストールした Playwright で `playwright install chromium` を実行してください。
- `.env` の `PLAYWRIGHT_BROWSERS_PATH` を指定した場合は、そのパスを優先します。

### 4. タスクスケジューラで定期実行する場合

1. スタートメニューで「タスク スケジューラ」を検索して開き、右側の「タスクの作成」を選びます。
2. **「全般」タブ**: 名前（例: `楽天ROOMコレクション登録`）を入力し、「ユーザーがログオンしているときのみ実行する」を選びます（ブラウザの画面を表示して操作するため）。
3. **「トリガー」タブ**: 「新規」→「毎日」と実行時刻を設定します。
   - 楽天ROOM自動投稿（`RakutenRoomAutoPost`、毎日18:00）で投稿した商品が対象になるため、**自動投稿が終わった後の時刻**（例: 19:00）にしてください。
4. **「操作」タブ**: 「新規」→「プログラムの開始」で、「プログラム/スクリプト」に `RakutenRoomCollection.exe` のフルパスを指定します。
   - 「開始（オプション）」は空欄で構いません。ログ（`logs`）とログインセッション（`user_data`）は、常に `RakutenRoomCollection.exe` と同じフォルダに作成されます。
5. 「OK」で保存し、一覧のタスクを右クリック →「実行する」で試しに動かして、`dist\logs` のログを確認します。

### 5. 別のパソコンで使う場合

- 「2. 実行時に必要な外部ファイル」の構成で、`RakutenRoomCollection.exe`・`.env`・`service_account.json` をコピーします（`user_data` と `logs` は不要です）。
- コピー先のパソコンでも Python と Playwright 1.40.0 をインストールし、`playwright install chromium` でブラウザをインストールしてください。

## ログ出力

ログファイルは `logs` フォルダに保存されます（1回の実行につき1ファイル）。

| 実行方法 | 保存先 |
|---|---|
| `python main.py` | プロジェクト直下の `logs` |
| `.exe` | `RakutenRoomCollection.exe` と同じフォルダの `logs`（例: `dist\logs`） |
| `.env` の `LOG_DIR` を指定した場合 | 指定したフォルダ |

- 実行時の作業フォルダ（どこから起動したか）には左右されません。
- ファイル名: `rakuten_room_collection_YYYYMMDD_HHMMSS.log`
- 登録対象の商品（行番号・商品コード・商品名）、コレクションごとの処理内容、商品ごとの結果、ログインの経過、失敗理由が記録されます。

出力例:

```
[INFO] 登録対象: 2コレクション / 3件
[INFO]   コレクション「キッチン」: 2件
[INFO]     行10 yamayuu:yj-5201 / 【 山崎実業 マグネット＆ウォール包丁ホルダー タワー W35 】 ...
[INFO] 作成済みのコレクション: 2件 ['キッチン', 'ガジェット']
[INFO] 作成済みのコレクション「キッチン」に追加登録します（2件）
[INFO] ✓ コレクション「キッチン」に1件を追加登録し、保存されたことを確認しました
[INFO] 【登録】「キッチン」に登録しました: yamayuu:yj-5201 / 【 山崎実業 ...
[INFO] 【登録済み】「キッチン」に登録済みでした: zwilling-shop:75002-823 / 【公式】 バッラリーニ ...
[INFO] CollectionStatusを「済」に更新しました（行: 10, 5）
[INFO] コレクション「インテリア」が無いため、新規作成します（1件）
[INFO] ジャンルが「すべてのジャンル」であることを確認しました
[WARNING] ROOMに投稿した商品の中に見つかりません: shop:item / 商品名
[INFO] 登録結果: 登録 1件 / 登録済み 1件 / 不可 1件 / 失敗 0件
[INFO] 楽天ROOMコレクション登録プログラムが完了しました
```

## トラブルシューティング

### 何も登録されない（「CollectionNameが未記入のため、登録対象外とした商品」と出る）
- スプレッドシートの CollectionName 列に、登録先のコレクション名を記入してください。
- PostStatus が「済」、CollectionStatus が「未」になっているか確認してください。

### CollectionStatus が「不可」になる
- 「ROOMに投稿した商品の中に見つかりません」: その商品がROOMに投稿されていないか、ItemURL がROOMの商品と異なります。ROOMに投稿済みか確認し、CollectionStatus を「未」に戻して再実行してください。
- 「コレクションの上限（100件）に達した」: 楽天ROOMのコレクションには100件までしか入りません。別のコレクション名にして、CollectionStatus を「未」に戻してください。

### 「登録中にエラーが発生しました」「【失敗】」と出る
- ログに出ているエラー内容と画面のURLを確認してください。CollectionStatus は「未」のままなので、次回の実行で自動的にもう一度登録を試します。
- 何度実行しても同じ場所で失敗する場合は、楽天ROOMの画面が変わった可能性があります。`room_collection.py` の先頭にある画面の部品（セレクタ）の見直しが必要です。

### 楽天へのログインに失敗する
- ログファイルの `[ERROR]` の行で原因を確認してください。
- 「パスワードを送信しましたがログインできませんでした」「ユーザーIDを送信しましたが次の画面に進めませんでした」
  - `.env` の `RAKUTEN_USER_ID`・`RAKUTEN_PASSWORD` が正しいか確認してください。
- 改善しない場合は `user_data` フォルダを削除してから再実行してください（ログインし直します）。
- 楽天にまったくつながらない場合は、楽天以外のサイト（yahoo.co.jp など）につながるかも確認してください（回線側の障害の可能性があります）。

### スプレッドシートに接続できない
- `SERVICE_ACCOUNT_PATH` のJSONファイルが存在するか確認してください。
- エラーに `Invalid argument` と出てパスが崩れている場合は、`.env` のパスをシングルクォートで囲んでください。
- スプレッドシートがサービスアカウントのメールアドレスに共有されているか確認してください。
- 「1行目に必須列が見つかりません」と出る場合は、見出し名が「[4. スプレッドシートの準備](#4-スプレッドシートの準備)」の表と一致しているか確認してください。

### ブラウザが起動しない
- `playwright install chromium` でブラウザをインストールしてください。

## ライセンス

このプログラムは個人使用を想定しています。

## 更新履歴

### v1.0 (2026-10-11)
- 楽天ROOMの実際の画面に合わせて全面的に作り直し
  - 作成済みのコレクションへの追加登録と、無い場合の新規作成（ジャンル「すべてのジャンル」を確認）
  - 商品の照合を ItemURL で行う（ROOMの商品名はショップ側で変わるため）
  - 保存後に編集画面を開き直し、商品が入ったことを確認してから「済」にする
  - 商品一覧を最後まで読み込めなかった場合や保存を確認できなかった場合は「未」のまま残し、次回再試行
  - 1つのコレクションで失敗しても、残りのコレクションの処理を続ける
  - コレクション名の全角・半角やスペースの違いを同じ名前として扱う
- ログイン方式を楽天ROOM自動投稿（RakutenRoom_AutoPost）と統一（セッション保存・パスキー回避・再認証）
- ログ・user_data の保存先をプログラムのフォルダに固定し、`.env` の `LOG_DIR` で変更可能に
- 登録・登録済み・不可・失敗の結果を商品ごとにログへ記録
- 自動テスト（pytest）と GitHub Actions での自動実行を追加
