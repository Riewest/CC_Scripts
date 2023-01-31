local util = {}


function util.findModem()
    for _, v in pairs( rs.getSides() ) do
          if peripheral.isPresent( v ) and peripheral.getType( v ) == "modem" then
            return true, v
          end
    end
    return false, nil
end


return util