using System;
using System.Collections.Generic;
using System.Drawing;
using System.Drawing.Text;
using System.Globalization;
using System.IO;
using System.Linq;
using ZiLib;
using ZiLib.FileVersion.Common;
using ZiLib.FileVersion.V5;

namespace ZiCli {
    internal static class Program {
        private static int Main(string[] args) {
            if (args.Length == 0) {
                PrintUsage();
                return 1;
            }

            try {
                switch (args[0].ToLowerInvariant()) {
                    case "inspect":
                        return RunInspect(args.Skip(1).ToArray());
                    case "generate":
                        return RunGenerate(args.Skip(1).ToArray());
                    default:
                        Console.Error.WriteLine("Unknown command.");
                        PrintUsage();
                        return 1;
                }
            } catch (Exception ex) {
                Console.Error.WriteLine("ERROR: " + ex.Message);
                return 2;
            }
        }

        private static int RunInspect(string[] args) {
            if (args.Length != 1) {
                Console.Error.WriteLine("inspect requires exactly one input file.");
                return 1;
            }

            var font = ZiFont.FromFile(args[0]);
            if (font == null) {
                throw new InvalidOperationException("Unable to parse .zi file.");
            }

            Console.WriteLine("name=" + font.Name);
            Console.WriteLine("version=" + font.Version);
            Console.WriteLine("codepage=" + font.CodePage.CodePageIdentifier);
            Console.WriteLine("height=" + font.CharacterHeight);
            Console.WriteLine("width=" + font.CharacterWidth);
            Console.WriteLine("characters=" + font.CharacterCount);
            Console.WriteLine("size=" + font.FileSize);
            return 0;
        }

        private static int RunGenerate(string[] args) {
            var options = ParseOptions(args);
            var output = Require(options, "out");
            var fontName = options.ContainsKey("font-name") ? options["font-name"] : null;
            var fontFile = options.ContainsKey("font-file") ? options["font-file"] : null;
            var ziName = options.ContainsKey("name") ? options["name"] : Path.GetFileNameWithoutExtension(output);
            var codePageText = options.ContainsKey("codepage") ? options["codepage"] : "utf-8";
            var height = ParseByte(options, "height", 32);
            var fontSize = ParseFloat(options, "font-size", height);
            var offsetX = ParseFloat(options, "offset-x", 0);
            var offsetY = ParseFloat(options, "offset-y", 0);
            var includeAscii = ParseBool(options, "include-ascii", true);

            var characters = LoadCharacters(options);
            if (includeAscii) {
                for (var value = 32; value <= 126; value++) {
                    characters.Add(Char.ConvertFromUtf32(value));
                }
            }
            if (characters.Count == 0) {
                throw new InvalidOperationException("No characters were provided.");
            }

            var codePageIdentifier = ParseCodePage(codePageText);
            var codePage = new CodePage(codePageIdentifier);
            var uniqueStrings = DeduplicateCharacters(characters);

            using (var fontResource = LoadFont(fontFile, fontName, fontSize)) {
                var ziFont = new ZiFontV5 {
                    Name = ziName,
                    CharacterHeight = height,
                    CharacterWidth = 0,
                    Orientation = FontOrientation.Vertical,
                    CodePage = codePage,
                };

                foreach (var ch in uniqueStrings) {
                    if (String.IsNullOrEmpty(ch)) {
                        continue;
                    }
                    var codePoint = Char.ConvertToUtf32(ch, 0);
                    var ziChar = new ZiCharacterV5(
                        ziFont,
                        (uint)codePoint,
                        fontResource.Font,
                        new PointF(offsetX, offsetY),
                        ch
                    );
                    ziFont.AddCharacter((uint)codePoint, ziChar);
                }

                var outputDir = Path.GetDirectoryName(Path.GetFullPath(output));
                if (!String.IsNullOrEmpty(outputDir) && !Directory.Exists(outputDir)) {
                    Directory.CreateDirectory(outputDir);
                }
                ziFont.Save(output);
            }

            Console.WriteLine("generated=" + Path.GetFullPath(output));
            Console.WriteLine("codepage=" + codePageIdentifier);
            Console.WriteLine("height=" + height);
            Console.WriteLine("font-size=" + fontSize.ToString(CultureInfo.InvariantCulture));
            Console.WriteLine("chars=" + DeduplicateCharacters(characters).Count);
            return 0;
        }

        private static HashSet<string> LoadCharacters(Dictionary<string, string> options) {
            var output = new HashSet<string>();
            if (options.ContainsKey("text")) {
                AddCharacters(output, options["text"]);
            }
            if (options.ContainsKey("text-file")) {
                AddCharacters(output, File.ReadAllText(options["text-file"]));
            }
            return output;
        }

        private static void AddCharacters(HashSet<string> output, string text) {
            if (String.IsNullOrEmpty(text)) {
                return;
            }
            for (var index = 0; index < text.Length; index++) {
                if (Char.IsHighSurrogate(text[index]) && index + 1 < text.Length && Char.IsLowSurrogate(text[index + 1])) {
                    output.Add(new string(new[] { text[index], text[index + 1] }));
                    index++;
                    continue;
                }

                var ch = text[index];
                if (ch == '\r' || ch == '\n') {
                    continue;
                }
                output.Add(ch.ToString());
            }
        }

        private static List<string> DeduplicateCharacters(IEnumerable<string> chars) {
            var seen = new HashSet<string>();
            var ordered = new List<string>();
            foreach (var item in chars) {
                if (String.IsNullOrEmpty(item)) {
                    continue;
                }
                if (seen.Add(item)) {
                    ordered.Add(item);
                }
            }
            return ordered;
        }

        private static IDisposableFont LoadFont(string fontFile, string fontName, float fontSize) {
            if (!String.IsNullOrEmpty(fontFile)) {
                var collection = new PrivateFontCollection();
                collection.AddFontFile(fontFile);
                if (collection.Families.Length == 0) {
                    collection.Dispose();
                    throw new InvalidOperationException("No font families found in font file.");
                }
                return new IDisposableFont(collection, new Font(collection.Families[0], fontSize, GraphicsUnit.Pixel));
            }

            if (String.IsNullOrEmpty(fontName)) {
                throw new InvalidOperationException("Either --font-name or --font-file is required.");
            }

            return new IDisposableFont(null, new Font(fontName, fontSize, GraphicsUnit.Pixel));
        }

        private static Dictionary<string, string> ParseOptions(string[] args) {
            var options = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
            for (var index = 0; index < args.Length; index++) {
                var token = args[index];
                if (!token.StartsWith("--", StringComparison.Ordinal)) {
                    throw new InvalidOperationException("Unexpected argument: " + token);
                }
                var key = token.Substring(2);
                if (index + 1 >= args.Length || args[index + 1].StartsWith("--", StringComparison.Ordinal)) {
                    options[key] = "true";
                    continue;
                }
                options[key] = args[++index];
            }
            return options;
        }

        private static string Require(Dictionary<string, string> options, string name) {
            if (!options.ContainsKey(name) || String.IsNullOrWhiteSpace(options[name])) {
                throw new InvalidOperationException("Missing required option --" + name);
            }
            return options[name];
        }

        private static byte ParseByte(Dictionary<string, string> options, string name, byte defaultValue) {
            if (!options.ContainsKey(name)) {
                return defaultValue;
            }
            return Byte.Parse(options[name], CultureInfo.InvariantCulture);
        }

        private static float ParseFloat(Dictionary<string, string> options, string name, float defaultValue) {
            if (!options.ContainsKey(name)) {
                return defaultValue;
            }
            return Single.Parse(options[name], CultureInfo.InvariantCulture);
        }

        private static bool ParseBool(Dictionary<string, string> options, string name, bool defaultValue) {
            if (!options.ContainsKey(name)) {
                return defaultValue;
            }
            var value = options[name];
            if (String.Equals(value, "true", StringComparison.OrdinalIgnoreCase) || value == "1") {
                return true;
            }
            if (String.Equals(value, "false", StringComparison.OrdinalIgnoreCase) || value == "0") {
                return false;
            }
            return defaultValue;
        }

        private static CodePageIdentifier ParseCodePage(string codePage) {
            switch (codePage.ToLowerInvariant()) {
                case "ascii":
                    return CodePageIdentifier.ASCII;
                case "gb2312":
                    return CodePageIdentifier.GB2312;
                case "utf-8":
                case "utf8":
                    return CodePageIdentifier.UTF_8;
                default:
                    throw new InvalidOperationException("Unsupported codepage: " + codePage);
            }
        }

        private static void PrintUsage() {
            Console.WriteLine("ZiCli inspect <font.zi>");
            Console.WriteLine("ZiCli generate --out out.zi [--font-name SimSun|--font-file file.ttf] --height 32 --font-size 32 --codepage utf-8 --text-file chars.txt [--text text] [--offset-x 0] [--offset-y 0] [--include-ascii true]");
        }

        private sealed class IDisposableFont : IDisposable {
            public PrivateFontCollection Collection { get; }
            public Font Font { get; }

            public IDisposableFont(PrivateFontCollection collection, Font font) {
                Collection = collection;
                Font = font;
            }

            public void Dispose() {
                Font.Dispose();
                if (Collection != null) {
                    Collection.Dispose();
                }
            }
        }
    }
}
