param(
    [Parameter(Mandatory = $true)]
    [string] $AssemblyPath,

    [Parameter(Mandatory = $true)]
    [string] $TypeName,

    [Parameter(Mandatory = $true)]
    [string] $MethodName
)

$ErrorActionPreference = 'Stop'
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$opCodes = @{}
foreach ($field in [System.Reflection.Emit.OpCodes].GetFields([System.Reflection.BindingFlags]'Public,Static')) {
    $op = [System.Reflection.Emit.OpCode] $field.GetValue($null)
    $opCodes[[int] $op.Value] = $op
}

function Format-Operand {
    param(
        [System.Reflection.Module] $Module,
        [System.Reflection.Emit.OpCode] $OpCode,
        [byte[]] $Il,
        [ref] $Offset
    )

    switch ($OpCode.OperandType) {
        ([System.Reflection.Emit.OperandType]::InlineNone) {
            return ''
        }
        ([System.Reflection.Emit.OperandType]::ShortInlineI) {
            $raw = [int] $Il[$Offset.Value]
            $value = if ($raw -gt 127) { $raw - 256 } else { $raw }
            $Offset.Value += 1
            return $value.ToString()
        }
        ([System.Reflection.Emit.OperandType]::InlineI) {
            $value = [BitConverter]::ToInt32($Il, $Offset.Value)
            $Offset.Value += 4
            return $value.ToString()
        }
        ([System.Reflection.Emit.OperandType]::InlineI8) {
            $value = [BitConverter]::ToInt64($Il, $Offset.Value)
            $Offset.Value += 8
            return $value.ToString()
        }
        ([System.Reflection.Emit.OperandType]::ShortInlineR) {
            $value = [BitConverter]::ToSingle($Il, $Offset.Value)
            $Offset.Value += 4
            return $value.ToString()
        }
        ([System.Reflection.Emit.OperandType]::InlineR) {
            $value = [BitConverter]::ToDouble($Il, $Offset.Value)
            $Offset.Value += 8
            return $value.ToString()
        }
        ([System.Reflection.Emit.OperandType]::ShortInlineBrTarget) {
            $raw = [int] $Il[$Offset.Value]
            $delta = if ($raw -gt 127) { $raw - 256 } else { $raw }
            $Offset.Value += 1
            return ('IL_{0:x4}' -f ($Offset.Value + $delta))
        }
        ([System.Reflection.Emit.OperandType]::InlineBrTarget) {
            $delta = [BitConverter]::ToInt32($Il, $Offset.Value)
            $Offset.Value += 4
            return ('IL_{0:x4}' -f ($Offset.Value + $delta))
        }
        ([System.Reflection.Emit.OperandType]::ShortInlineVar) {
            $value = $Il[$Offset.Value]
            $Offset.Value += 1
            return $value.ToString()
        }
        ([System.Reflection.Emit.OperandType]::InlineVar) {
            $value = [BitConverter]::ToUInt16($Il, $Offset.Value)
            $Offset.Value += 2
            return $value.ToString()
        }
        ([System.Reflection.Emit.OperandType]::InlineString) {
            $token = [BitConverter]::ToInt32($Il, $Offset.Value)
            $Offset.Value += 4
            try {
                return '"' + $Module.ResolveString($token) + '"'
            } catch {
                return ('string-token 0x{0:x8}' -f $token)
            }
        }
        ([System.Reflection.Emit.OperandType]::InlineField) {
            $token = [BitConverter]::ToInt32($Il, $Offset.Value)
            $Offset.Value += 4
            try {
                $field = $Module.ResolveField($token)
                return $field.DeclaringType.FullName + '::' + $field.Name
            } catch {
                return ('field-token 0x{0:x8}' -f $token)
            }
        }
        ([System.Reflection.Emit.OperandType]::InlineMethod) {
            $token = [BitConverter]::ToInt32($Il, $Offset.Value)
            $Offset.Value += 4
            try {
                $method = $Module.ResolveMethod($token)
                return $method.DeclaringType.FullName + '::' + $method.Name + ' ' + $method.ToString()
            } catch {
                return ('method-token 0x{0:x8}' -f $token)
            }
        }
        ([System.Reflection.Emit.OperandType]::InlineType) {
            $token = [BitConverter]::ToInt32($Il, $Offset.Value)
            $Offset.Value += 4
            try {
                return $Module.ResolveType($token).FullName
            } catch {
                return ('type-token 0x{0:x8}' -f $token)
            }
        }
        ([System.Reflection.Emit.OperandType]::InlineTok) {
            $token = [BitConverter]::ToInt32($Il, $Offset.Value)
            $Offset.Value += 4
            try {
                $member = $Module.ResolveMember($token)
                return $member.DeclaringType.FullName + '::' + $member.Name
            } catch {
                return ('member-token 0x{0:x8}' -f $token)
            }
        }
        ([System.Reflection.Emit.OperandType]::InlineSwitch) {
            $count = [BitConverter]::ToInt32($Il, $Offset.Value)
            $Offset.Value += 4
            $targets = New-Object string[] $count
            $baseOffset = $Offset.Value + ($count * 4)
            for ($i = 0; $i -lt $count; $i++) {
                $delta = [BitConverter]::ToInt32($Il, $Offset.Value)
                $Offset.Value += 4
                $targets[$i] = ('IL_{0:x4}' -f ($baseOffset + $delta))
            }
            return '(' + ($targets -join ', ') + ')'
        }
        default {
            throw "Unsupported operand type: $($OpCode.OperandType)"
        }
    }
}

$assembly = [System.Reflection.Assembly]::LoadFile((Resolve-Path -LiteralPath $AssemblyPath))
$type = $assembly.GetType($TypeName, $true)
$methods = $type.GetMethods([System.Reflection.BindingFlags]'Public,NonPublic,Static,Instance,DeclaredOnly') |
    Where-Object { $_.Name -eq $MethodName }

if ($methods.Count -eq 0) {
    throw "Method not found: $TypeName.$MethodName"
}

foreach ($method in $methods) {
    Write-Output ('# ' + $method.ToString())
    $body = $method.GetMethodBody()
    if ($null -eq $body) {
        Write-Output '# No method body.'
        continue
    }

    $locals = $body.LocalVariables | ForEach-Object {
        ('[{0}] {1}' -f $_.LocalIndex, $_.LocalType.FullName)
    }
    if ($locals) {
        Write-Output ('# Locals: ' + ($locals -join '; '))
    }

    $il = $body.GetILAsByteArray()
    $offset = 0
    while ($offset -lt $il.Length) {
        $start = $offset
        $code = [int] $il[$offset]
        $offset += 1
        if ($code -eq 0xfe) {
            $code = 0xfe00 -bor [int] $il[$offset]
            $offset += 1
        }

        $op = $opCodes[$code]
        if ($null -eq $op) {
            throw ('Unknown opcode 0x{0:x} at IL_{1:x4}' -f $code, $start)
        }

        $offsetRef = [ref] $offset
        $operand = Format-Operand -Module $method.Module -OpCode $op -Il $il -Offset $offsetRef
        $offset = $offsetRef.Value
        if ([string]::IsNullOrWhiteSpace($operand)) {
            Write-Output ('IL_{0:x4}: {1}' -f $start, $op.Name)
        } else {
            Write-Output ('IL_{0:x4}: {1,-12} {2}' -f $start, $op.Name, $operand)
        }
    }
}
